FROM python:3.9
RUN mkdir /src
ADD handlers.py /src
RUN pip3 install kopf kubernetes
CMD kopf run /src/handlers.py --verbose