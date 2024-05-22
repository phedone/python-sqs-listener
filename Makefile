local_build:
	python setup.py bdist_wheel

localq:
	docker run --rm -d -it -p 4566:4566 -e AWS_ACCESS_KEY=test -e AWS_SECRET_ACCESS_KEY=test -p 4510-4559:4510-4559  localstack/localstack

createq:
	# Need to preinstall aws cli and awslocal cli
	# run aws configure
	# key=test secret_key=test region=ap-northeast-1
	awslocal --endpoint-url=http://localhost:4566 sqs create-queue --queue-name test_queue
	awslocal --endpoint-url=http://localhost:4566 sqs create-queue --queue-name test_queue_d

test:
	python test.py

lint:
	pylama ./sqs_launcher
	pylama ./sqs_queue
	pylama ./sqs_listener
