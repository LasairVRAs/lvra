import json
from lasair import lasair_consumer                            # line A          

kafka_server = 'lasair-lsst-dev-kafka_pub.lsst.ac.uk:9092'            # line B
my_topic     = 'lasair_83vra-dev'                          # line C
group_id     = 'test_ox7'                                      # line D       
consumer = lasair_consumer(kafka_server, group_id, my_topic)


n = 0
while n < 4000:
    msg = consumer.poll(timeout=20)
    if msg is None:
        break
    if msg.error():
        print(str(msg.error()))
        break
    result = json.loads(msg.value())
    _id = result['diaObjectId']
    print(f'{_id}')
    with open(f'./json/{_id}.json', 'a') as file:
        json.dump(result,file, indent=2)

    n += 1
print(n, 'messages')

