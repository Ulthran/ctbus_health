from aws_cdk import (
    CfnOutput,
    CustomResource,
    Duration,
    Stack,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_sqs as sqs,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    aws_lambda_event_sources as eventsources,
    custom_resources as cr
)
from constructs import Construct

class CtbusHealthIngestStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Use Default VPC
        vpc = ec2.Vpc.from_lookup(self, "DefaultVPC", is_default=True)

        # SQS Queue
        queue = sqs.Queue(self, "CtbusHealthQueue")

        # Security Groups
        lambda_sg = ec2.SecurityGroup(self, "CtbusHealthIngestLambdaSG", vpc=vpc)
        aurora_sg = ec2.SecurityGroup(self, "CtbusHealthAuroraSG", vpc=vpc)
        
        aurora_sg.add_ingress_rule(lambda_sg, ec2.Port.tcp(5432), "Allow Lambda access to Aurora")

        # Secrets Manager for DB Credentials
        db_secret = secretsmanager.Secret(self, "CtbusHealthAuroraSecret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "postgres"}',
                exclude_punctuation=True
            )
        )

        # Aurora Serverless v2 (PostgreSQL)
        aurora_cluster = rds.DatabaseCluster(self, "CtbusHealthAuroraCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(version=rds.AuroraPostgresEngineVersion.VER_13_6),
            credentials=rds.Credentials.from_secret(db_secret),
            default_database_name="healthdb",
            vpc=vpc,
            vpc_subnets={"subnet_type": ec2.SubnetType.PRIVATE_WITH_EGRESS},
            security_groups=[aurora_sg],
            removal_policy=RemovalPolicy.DESTROY
        )

        # Lambda Function to Initialize Schema
        init_lambda = _lambda.Function(self, "CtbusHealthSchemaInitLambda",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("schema_init_lambda"),
            vpc=vpc,
            environment={
                "DB_SECRET_ARN": db_secret.secret_arn,
                "DB_HOST": aurora_cluster.cluster_endpoint.hostname,
                "DB_NAME": "healthdb"
            }
        )

        db_secret.grant_read(init_lambda)
        aurora_cluster.grant_connect(init_lambda)

        # Custom Resource to Trigger Schema Setup
        provider = cr.Provider(self, "SchemaProvider",
            on_event_handler=init_lambda
        )

        CustomResource(self, "SchemaInitResource", service_token=provider.service_token)

        # IAM Role for Lambda
        lambda_role = iam.Role(self, "CtbusHealthIngestLambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Grant Lambda permissions to call Bedrock API
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:ListFoundationModels",
                    "bedrock:GetModelInvocationLoggingConfiguration"
                ],
                resources=["*"]
            )
        )

        # Grant Lambda permissions to access SQS, Secrets Manager, and Aurora
        queue.grant_consume_messages(lambda_role)
        db_secret.grant_read(lambda_role)
        aurora_cluster.grant_connect(lambda_role)

        # Lambda Function
        lambda_function = _lambda.Function(self, "CtbusHealthIngestLambda",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),
            vpc=vpc,
            security_groups=[lambda_sg],
            environment={
                "SQS_QUEUE_URL": queue.queue_url,
                "DB_SECRET_ARN": db_secret.secret_arn,
                "DB_HOST": aurora_cluster.cluster_endpoint.hostname,
                "DB_NAME": "healthdb"
            },
            role=lambda_role,
            timeout=Duration.seconds(30)
        )

        # Connect SQS to Lambda
        lambda_function.add_event_source(eventsources.SqsEventSource(queue, batch_size=1)) # TODO: Up batch size maybe

        # Outputs
        CfnOutput(self, "AuroraEndpoint", value=aurora_cluster.cluster_endpoint.hostname)