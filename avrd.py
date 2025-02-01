import RPi.GPIO as GPIO
from flask import Flask, render_template, Response
from flask_socketio import SocketIO
import gps
import time
import math
import cv2

GPIO.setmode(GPIO.BCM)
motor_pins = {
    'motorA_in1': 17,
    'motorA_in2': 18,
    'motorB_in1': 22,
    'motorB_in2': 23,
    'headlights': 24
}

for pin in motor_pins.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

app = Flask(__name__)
socketio = SocketIO(app)

session = gps.gps(mode=gps.WATCH_ENABLE)

destination = None
current_location = {'lat': 0, 'lon': 0}

# Start the webcam stream (OpenCV)
camera = cv2.VideoCapture(0)

@app.route('/')
def index():
    return render_template('index.html')

def get_gps_data():
    global destination, current_location
    while True:
        report = session.next()
        if report['class'] == 'TPV':
            current_location['lat'] = report.lat
            current_location['lon'] = report.lon
            socketio.emit('gps_data', {'lat': current_location['lat'], 'lon': current_location['lon']})
            if destination:
                navigate_to_destination(current_location['lat'], current_location['lon'])
            socketio.sleep(1)

def navigate_to_destination(current_lat, current_lon):
    global destination
    dest_lat, dest_lon = destination
    distance = math.sqrt((dest_lat - current_lat)**2 + (dest_lon - current_lon)**2)
    if distance < 0.0001:
        stop_robot()
        destination = None
        print("Destination Reached!")
    else:
        move_forward()

def move_forward():
    GPIO.output(motor_pins['motorA_in1'], GPIO.HIGH)
    GPIO.output(motor_pins['motorA_in2'], GPIO.LOW)
    GPIO.output(motor_pins['motorB_in1'], GPIO.HIGH)
    GPIO.output(motor_pins['motorB_in2'], GPIO.LOW)

def stop_robot():
    for pin in motor_pins.values():
        GPIO.output(pin, GPIO.LOW)

@socketio.on('set_destination')
def set_destination(data):
    global destination
    destination = (data['lat'], data['lon'])
    print(f"New Destination Set: {destination}")

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            ret, frame = camera.read()
            if not ret:
                break
            # Convert the frame to JPEG format
            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            # Yield the JPEG frame as MJPEG stream
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    socketio.start_background_task(target=get_gps_data)
    socketio.run(app, host='0.0.0.0', port=5000)
