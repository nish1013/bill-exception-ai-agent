resource "aws_ecs_cluster" "main" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_service_discovery_http_namespace" "main" {
  name = var.name
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.name}"
  retention_in_days = 30
}

locals {
  secret_arn = { for key, secret in aws_secretsmanager_secret.app : key => secret.arn }

  app_environment = {
    DJANGO_ALLOWED_HOSTS = "*"
    POSTGRES_HOST        = aws_db_instance.postgres.address
    POSTGRES_DB          = "payables"
    POSTGRES_USER        = "payables"
    POSTGRES_APP_USER    = "payables_app"
    POSTGRES_RELAY_USER  = "payables_relay"
    REDIS_URL            = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"
    OIDC_ISSUER          = var.oidc_issuer
    OIDC_JWKS_URL        = "${var.oidc_issuer}/jwks"
    OIDC_AUDIENCE        = var.oidc_audience
  }

  app_secrets = {
    DJANGO_SECRET_KEY       = local.secret_arn["django-secret-key"]
    POSTGRES_PASSWORD       = "${aws_db_instance.postgres.master_user_secret[0].secret_arn}:password::"
    POSTGRES_APP_PASSWORD   = local.secret_arn["postgres-app-password"]
    POSTGRES_RELAY_PASSWORD = local.secret_arn["postgres-relay-password"]
    CELERY_BROKER_URL       = local.secret_arn["broker-url"]
  }

  # One image, one command per service (D50). Concurrency and queues match docker-compose.yml.
  app_services = {
    api = {
      command     = null
      cpu         = 512
      memory      = 1024
      count       = 2
      port        = 8000
      environment = {}
      secrets     = { ACCOUNTING_CALLBACK_SECRET = local.secret_arn["accounting-callback-secret"] }
    }
    relay = {
      command     = ["python", "manage.py", "run_relay"]
      cpu         = 256
      memory      = 512
      count       = 1
      port        = null
      environment = {}
      secrets     = {}
    }
    worker-checks = {
      command     = ["celery", "-A", "config", "worker", "-Q", "checks", "-c", "4"]
      cpu         = 512
      memory      = 1024
      count       = 1
      port        = null
      environment = {}
      secrets     = {}
    }
    # Only this service holds the model key (D54).
    worker-propose-ai = {
      command = ["celery", "-A", "config", "worker", "-Q", "propose-ai", "-c", "2"]
      cpu     = 512
      memory  = 1024
      count   = 1
      port    = null
      environment = {
        LLM_PROVIDER = var.llm_provider
        LLM_MODEL    = var.llm_model
      }
      secrets = { OPENAI_API_KEY = local.secret_arn["openai-api-key"] }
    }
    worker-apply = {
      command     = ["celery", "-A", "config", "worker", "-Q", "apply", "-c", "2"]
      cpu         = 256
      memory      = 512
      count       = 1
      port        = null
      environment = { ACCOUNTING_CALLBACK_URL = "http://api:8000/callbacks/accounting/stub" }
      secrets     = { ACCOUNTING_CALLBACK_SECRET = local.secret_arn["accounting-callback-secret"] }
    }
    worker-reports = {
      command     = ["celery", "-A", "config", "worker", "-Q", "reports", "-c", "1"]
      cpu         = 256
      memory      = 512
      count       = 1
      port        = null
      environment = {}
      secrets     = {}
    }
  }
}

resource "aws_ecs_task_definition" "app" {
  for_each = local.app_services

  family                   = "${var.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.execution[each.key].arn

  container_definitions = jsonencode([{
    name      = each.key
    image     = var.api_image
    command   = each.value.command
    essential = true
    portMappings = each.value.port == null ? [] : [{
      name          = each.key
      containerPort = each.value.port
    }]
    environment = [
      for key, value in merge(local.app_environment, each.value.environment) :
      { name = key, value = value }
    ]
    secrets = [
      for key, arn in merge(local.app_secrets, each.value.secrets) :
      { name = key, valueFrom = arn }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = each.key
      }
    }
  }])
}

resource "aws_ecs_service" "app" {
  for_each = local.app_services

  name            = each.key
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app[each.key].arn
  desired_count   = each.value.count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.tasks.id]
  }

  # The web and worker-apply services reach the API by the name "api".
  service_connect_configuration {
    enabled   = true
    namespace = aws_service_discovery_http_namespace.main.arn

    dynamic "service" {
      for_each = each.value.port == null ? [] : [each.value.port]
      content {
        port_name = each.key
        client_alias {
          dns_name = each.key
          port     = service.value
        }
      }
    }
  }

  dynamic "load_balancer" {
    for_each = each.key == "api" ? [aws_lb_target_group.api.arn] : []
    content {
      target_group_arn = load_balancer.value
      container_name   = "api"
      container_port   = 8000
    }
  }
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${var.name}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution["web"].arn

  # The console container holds no database, broker or signing secret.
  container_definitions = jsonencode([{
    name         = "web"
    image        = var.web_image
    essential    = true
    portMappings = [{ name = "web", containerPort = 8080 }]
    environment = [
      { name = "API_UPSTREAM", value = "api:8000" },
      { name = "OIDC_ORIGIN", value = var.oidc_issuer },
    ]
    linuxParameters = { capabilities = { drop = ["ALL"] } }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "web"
      }
    }
  }])
}

resource "aws_ecs_service" "web" {
  name            = "web"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.tasks.id]
  }

  service_connect_configuration {
    enabled   = true
    namespace = aws_service_discovery_http_namespace.main.arn
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 8080
  }
}

# Migrations run as a one-off task of this definition before a deploy of the services.
resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.name}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution["api"].arn

  container_definitions = jsonencode([{
    name        = "migrate"
    image       = var.api_image
    command     = ["python", "manage.py", "migrate", "--database", "owner", "--noinput"]
    essential   = true
    environment = [for key, value in local.app_environment : { name = key, value = value }]
    secrets     = [for key, arn in local.app_secrets : { name = key, valueFrom = arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "migrate"
      }
    }
  }])
}
