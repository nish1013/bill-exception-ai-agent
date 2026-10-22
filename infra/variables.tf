variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "name" {
  type    = string
  default = "payables"
}

variable "vpc_id" {
  type        = string
  description = "An existing VPC. The sketch does not create the network."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Subnets for the load balancer."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Subnets for the tasks, the database, Redis and the broker."
}

variable "certificate_arn" {
  type        = string
  description = "The TLS certificate of the console host name."
}

variable "api_image" {
  type        = string
  description = "One image for the API, the relay and each worker (D50)."
}

variable "web_image" {
  type = string
}

variable "oidc_issuer" {
  type        = string
  description = "The tenant's OIDC provider. Its tokens carry tenant_id and role claims (D15)."
}

variable "oidc_audience" {
  type    = string
  default = "payables-api"
}

variable "llm_provider" {
  type    = string
  default = "stub"

  validation {
    condition     = contains(["stub", "openai"], var.llm_provider)
    error_message = "llm_provider is stub or openai."
  }
}

variable "llm_model" {
  type        = string
  default     = ""
  description = "The pinned model id when llm_provider is openai (D54)."
}
