output "console_dns_name" {
  value = aws_lb.main.dns_name
}

output "migrate_task_definition" {
  value = aws_ecs_task_definition.migrate.arn
}

output "broker_endpoint" {
  value = aws_mq_broker.rabbitmq.instances[0].endpoints[0]
}
