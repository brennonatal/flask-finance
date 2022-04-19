FROM ubuntu:latest

RUN apt-get update -y && \
    apt-get install -y python3-pip

COPY ./requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip install -r requirements.txt

COPY . /app

ENV API_KEY=...

ENTRYPOINT [ "python3" ]

CMD [ "app.py" ]