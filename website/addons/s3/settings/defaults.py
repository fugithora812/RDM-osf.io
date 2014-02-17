import json

from website.settings import DOMAIN

MAX_RENDER_SIZE = (1024 ** 2) * 3

ALLOWED_ORIGIN = DOMAIN
CORS_RULE = (
    '<CORSRule>'
    '<AllowedMethod>PUT</AllowedMethod>'
    '<AllowedMethod>GET</AllowedMethod>'
    '<AllowedOrigin>' + ALLOWED_ORIGIN + '</AllowedOrigin>'
    '<AllowedHeader>*</AllowedHeader>'
    '</CORSRule>'

)
OSF_USER = 'osf-user{0}'
OSF_USER_POLICY_NAME = 'osf-user-policy'
OSF_USER_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "Stmt1392138408000",
                "Effect": "Allow",
                "Action": [
                    "s3:*"
                ],
                "Resource": [
                    "*"
                ]
            },
            {
                "Sid": "Stmt1392138440000",
                "Effect": "Allow",
                "Action": [
                    "iam:DeleteAccessKey",
                    "iam:DeleteUser",
                    "iam:DeleteUserPolicy"
                ],
                "Resource": [
                    "*"
                ]
            }
        ]
    }
)
