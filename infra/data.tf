# Postgres holds all state. Redis and RabbitMQ hold nothing that a restart cannot rebuild.

resource "aws_db_subnet_group" "main" {
  name       = var.name
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "postgres" {
  identifier                  = var.name
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = "db.t4g.medium"
  allocated_storage           = 20
  db_name                     = "payables"
  username                    = "payables"
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.main.name
  vpc_security_group_ids      = [aws_security_group.data.id]
  storage_encrypted           = true
  backup_retention_period     = 7
  deletion_protection         = true
  skip_final_snapshot         = false
  final_snapshot_identifier   = "${var.name}-final"
}

resource "aws_elasticache_subnet_group" "main" {
  name       = var.name
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id         = var.name
  engine             = "redis"
  engine_version     = "7.1"
  node_type          = "cache.t4g.small"
  num_cache_nodes    = 1
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.data.id]
}

resource "aws_mq_broker" "rabbitmq" {
  broker_name                = var.name
  engine_type                = "RabbitMQ"
  engine_version             = "3.13"
  host_instance_type         = "mq.t3.micro"
  deployment_mode            = "SINGLE_INSTANCE"
  auto_minor_version_upgrade = true
  publicly_accessible        = false
  subnet_ids                 = [var.private_subnet_ids[0]]
  security_groups            = [aws_security_group.data.id]

  user {
    username = "payables"
    password = random_password.broker.result
  }
}

resource "random_password" "broker" {
  length  = 32
  special = false
}

# Each secret is set outside Terraform. A task reads only the secrets that its service names.
resource "aws_secretsmanager_secret" "app" {
  for_each = toset([
    "django-secret-key",
    "postgres-app-password",
    "postgres-relay-password",
    "broker-url",
    "accounting-callback-secret",
    "openai-api-key",
  ])
  name = "${var.name}/${each.key}"
}
