import paho.mqtt.client as mqtt

class BrokerClient:
    def __init__(self, topic, on_message_callback):
        self.client = mqtt.Client()
        self.client.tls_set()
        self.client.on_connect = self.on_connect
        self.client.on_message = on_message_callback
        self.topic = topic
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self.topic)    
        else:
            print("Connecting error to the broker", rc)
    def start(self):
        self.client.connect("broker.hivemq.com", port=8883)
        self.client.loop_start()
    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()