import json
from lasair import lasair_consumer                            # line A          
import yaml
import logging 

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s")

with open('../data/settings.yaml', 'r') as settings:
    config = yaml.safe_load(settings)
    kafka_server = config['kafka_server']
    my_topic = config['my_topic']
    group_id = config['group_id']
    json_data_dir = config['json_data_dir']

def main():
    consumer = lasair_consumer(kafka_server, group_id, my_topic)
    
    n = 0
    while n < 4000:
        msg = consumer.poll(timeout=20)
        if msg is None:
            break
        if msg.error():
            logger.info(f'{str(msg.error())}')
            break
        result = json.loads(msg.value())
        _id = result['diaObjectId']
        logger.info(f'Got data for: {_id}')
        # TODO: Roy suggested making one directory per day which could be a useful way to organise the 
        # data if it starts piling up 
        with open(f'{json_data_dir}/{_id}.json', 'a') as file:
            json.dump(result,file, indent=2)
    
        n += 1
    logger.info(f'{n} messages received')
    return 0

if __name__=='__main__':
    main()
