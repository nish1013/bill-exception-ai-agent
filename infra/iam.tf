data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

locals {
  # Each service reads only the secrets that its task definition names.
  service_secret_arns = merge(
    {
      for key, service in local.app_services :
      key => distinct([
        for arn in values(merge(local.app_secrets, service.secrets)) : split(":password::", arn)[0]
      ])
    },
    { web = [] },
  )
}

resource "aws_iam_role" "execution" {
  for_each = local.service_secret_arns

  name               = "${var.name}-${each.key}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  for_each = local.service_secret_arns

  role       = aws_iam_role.execution[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "read_secrets" {
  for_each = { for key, arns in local.service_secret_arns : key => arns if length(arns) > 0 }

  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = each.value
  }
}

resource "aws_iam_role_policy" "read_secrets" {
  for_each = data.aws_iam_policy_document.read_secrets

  name   = "read-secrets"
  role   = aws_iam_role.execution[each.key].id
  policy = each.value.json
}
