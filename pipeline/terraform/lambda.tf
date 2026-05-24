# Listener

data "archive_file" "listener" {
  type        = "zip"
  source_file = "${path.module}/../listener/index.py"
  output_path = "${path.module}/build/listener.zip"
}

resource "aws_iam_role" "listener" {
  name = "ctbus-food-listener"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "listener_logs" {
  role       = aws_iam_role.listener.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "listener" {
  role = aws_iam_role.listener.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = [
          aws_ssm_parameter.telegram_bot_token.arn,
          aws_ssm_parameter.telegram_webhook_secret.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${var.aws_region}.amazonaws.com"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.health_data.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.food_queue.arn
      },
    ]
  })
}

resource "aws_lambda_function" "listener" {
  function_name    = "ctbus-food-listener"
  role             = aws_iam_role.listener.arn
  runtime          = "python3.13"
  handler          = "index.lambda_handler"
  filename         = data.archive_file.listener.output_path
  source_code_hash = data.archive_file.listener.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      BUCKET_NAME          = aws_s3_bucket.health_data.bucket
      QUEUE_URL            = aws_sqs_queue.food_queue.url
      BOT_TOKEN_PARAM      = aws_ssm_parameter.telegram_bot_token.name
      WEBHOOK_SECRET_PARAM = aws_ssm_parameter.telegram_webhook_secret.name
    }
  }
}

resource "aws_lambda_permission" "listener_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.listener.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.telegram.execution_arn}/*/*"
}

# pyzbar Lambda Layer
# Run pipeline/build_pyzbar_layer.sh before the first `terraform apply`.

resource "aws_lambda_layer_version" "pyzbar" {
  layer_name               = "ctbus-pyzbar"
  filename                 = "${path.module}/build/pyzbar_layer.zip"
  source_code_hash         = filebase64sha256("${path.module}/build/pyzbar_layer.zip")
  compatible_runtimes      = ["python3.13"]
  compatible_architectures = ["x86_64"]
}

# Processor

data "archive_file" "processor" {
  type        = "zip"
  source_file = "${path.module}/../processor/index.py"
  output_path = "${path.module}/build/processor.zip"
}

resource "aws_iam_role" "processor" {
  name = "ctbus-food-processor"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "processor_logs" {
  role       = aws_iam_role.processor.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "processor" {
  role = aws_iam_role.processor.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.health_data.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.health_data.arn
      },
      {
        Effect   = "Allow"
        Action   = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = aws_sqs_queue.food_queue.arn
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = [
          aws_ssm_parameter.usda_api_key.arn,
          aws_ssm_parameter.tavily_api_key.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${var.aws_region}.amazonaws.com"
          }
        }
      },
    ]
  })
}

resource "aws_lambda_function" "processor" {
  function_name                  = "ctbus-food-processor"
  role                           = aws_iam_role.processor.arn
  runtime                        = "python3.13"
  handler                        = "index.lambda_handler"
  filename                       = data.archive_file.processor.output_path
  source_code_hash               = data.archive_file.processor.output_base64sha256
  timeout                        = 300
  memory_size                    = 512
  reserved_concurrent_executions = 1
  layers                         = [aws_lambda_layer_version.pyzbar.arn]

  environment {
    variables = {
      BUCKET_NAME           = aws_s3_bucket.health_data.bucket
      BEDROCK_MODEL_ID      = var.bedrock_model_id
      USDA_API_KEY_PARAM    = aws_ssm_parameter.usda_api_key.name
      TAVILY_API_KEY_PARAM  = aws_ssm_parameter.tavily_api_key.name
    }
  }
}

resource "aws_lambda_event_source_mapping" "processor_sqs" {
  event_source_arn                   = aws_sqs_queue.food_queue.arn
  function_name                      = aws_lambda_function.processor.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5
}
