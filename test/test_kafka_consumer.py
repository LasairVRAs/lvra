from lvra.kafka_consumer import main

def test_kafka_consumer():
    exit_code = main()
    assert exit_code == 0, "something went wrong!"

