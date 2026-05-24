data "archive_file" "cognito_presignup" {
  type        = "zip"
  source_file = "${path.module}/../cognito_presignup/index.py"
  output_path = "${path.module}/build/cognito_presignup.zip"
}

resource "aws_iam_role" "cognito_presignup" {
  name = "ctbus-food-cognito-presignup"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "cognito_presignup_logs" {
  role       = aws_iam_role.cognito_presignup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "cognito_presignup" {
  function_name    = "ctbus-food-cognito-presignup"
  role             = aws_iam_role.cognito_presignup.arn
  runtime          = "python3.13"
  handler          = "index.lambda_handler"
  filename         = data.archive_file.cognito_presignup.output_path
  source_code_hash = data.archive_file.cognito_presignup.output_base64sha256
  timeout          = 5
  memory_size      = 128

  environment {
    variables = {
      ALLOWED_EMAILS = join(",", var.allowed_emails)
    }
  }
}

resource "aws_lambda_permission" "cognito_presignup" {
  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cognito_presignup.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.main.arn
}

resource "aws_cognito_user_pool" "main" {
  name                     = "ctbus-food-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  lambda_config {
    pre_sign_up = aws_lambda_function.cognito_presignup.arn
  }
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "ctbus-food-auth"
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_identity_provider" "google" {
  user_pool_id  = aws_cognito_user_pool.main.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id                     = var.google_client_id
    client_secret                 = var.google_client_secret
    authorize_scopes              = "email profile openid"
    attributes_url                = "https://people.googleapis.com/v1/people/me?personFields="
    attributes_url_add_attributes = "true"
    authorize_url                 = "https://accounts.google.com/o/oauth2/v2/auth"
    oidc_issuer                   = "https://accounts.google.com"
    token_request_method          = "POST"
    token_url                     = "https://oauth2.googleapis.com/token"
  }

  attribute_mapping = {
    email    = "email"
    username = "sub"
  }
}

resource "aws_cognito_user_pool_client" "frontend" {
  name         = "ctbus-food-frontend"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["email", "openid", "profile"]

  callback_urls = [
    "https://${var.domain_name}/callback",
    "http://localhost:8081/callback",
  ]
  logout_urls = [
    "https://${var.domain_name}",
    "http://localhost:8081",
  ]

  supported_identity_providers = ["Google"]

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  explicit_auth_flows = ["ALLOW_REFRESH_TOKEN_AUTH"]

  depends_on = [aws_cognito_identity_provider.google]
}
