from kombu import Connection, Exchange, Queue

CHECKS = "checks"
DEAD_LETTER_SUFFIX = ".dlq"


def dead_letter_name(queue: str) -> str:
    return f"{queue}{DEAD_LETTER_SUFFIX}"


def work_queue(name: str) -> Queue:
    # A rejected message goes to <queue>.dlq through the default exchange (D17, D43).
    return Queue(
        name,
        Exchange(name, type="direct"),
        routing_key=name,
        durable=True,
        queue_arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": dead_letter_name(name),
        },
    )


def dead_letter_queue(name: str) -> Queue:
    dead_letters = dead_letter_name(name)
    return Queue(dead_letters, Exchange(dead_letters, type="direct"), routing_key=dead_letters)


WORK_QUEUES = (work_queue(CHECKS),)
DEAD_LETTER_QUEUES = (dead_letter_queue(CHECKS),)
ALL_QUEUES = WORK_QUEUES + DEAD_LETTER_QUEUES


def declare_queues(connection: Connection) -> None:
    # RabbitMQ drops a rejected message when its dead-letter queue does not exist yet.
    channel = connection.default_channel
    for queue in ALL_QUEUES:
        queue.bind(channel).declare()
