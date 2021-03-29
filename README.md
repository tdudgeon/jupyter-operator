# Jupyter Operator

This repo is an experiment to create a simple Kubernetes (K8S) Operator that can be used to create
Jupyter Notebooks within  a K8S cluster.

What this repo is trying to do is pull out only what is essential for deploying ONLY the Jupyter operator
to the cluster.

**NOTE**: this work is preliminary and far from fully functional.

## My environment

Minukube  with these addons enabled:
* default-storageclass
* ingress
* ingress-dns
* storage-provisioner

Python 3.9.1 with kopf and kubernetes installed with Pip.
I use a Conda environment.

## Deployment Steps

### Deploy the CRD

```
$ kubectl create -f crd.yaml
```

### Run the operator

For testing the operator is run manually from Python.
This needs the INGRESS_DOMAIN environment variable to be set to the base domain name for the K8S cluster:
```
export INGRESS_DOMAIN=192.168.49.2.nip.io
```

```
$ kopf run handlers.py 
[2021-01-20 16:31:09,827] kopf.reactor.activit [INFO    ] Initial authentication has been initiated.
[2021-01-20 16:31:09,830] kopf.activities.auth [INFO    ] Activity 'login_via_pykube' succeeded.
[2021-01-20 16:31:09,834] kopf.activities.auth [INFO    ] Activity 'login_via_client' succeeded.
[2021-01-20 16:31:09,834] kopf.reactor.activit [INFO    ] Initial authentication has finished.
[2021-01-20 16:31:09,844] kopf.engines.peering [WARNING ] Default peering object not found, falling back to the standalone mode.
```


### Example notebook

```
$ kubectl create -f notebook-2.yaml 
jupyternotebook.jupyter-on-kubernetes.test/notebook created
```

This deploys a very basic notebook environment. notebook-3 and notebook-4 illustrate other options.

In the kopf logs you see this:
```
[2021-01-20 16:12:42,393] kopf.objects         [INFO    ] [default/notebook] Handler 'jupyter' succeeded.
[2021-01-20 16:12:42,393] kopf.objects         [INFO    ] [default/notebook] Creation event is processed: 1 succeeded; 0 failed.
```

Check what has been created:
```
$ kubectl get jupyternotebooks.squonk.it
NAME       URL   PASSWORD
notebook   http://notebook-default.192.168.49.2.nip.io/?token=CWM8PsfayLpd1qFj   CWM8PsfayLpd1qFj      
```

See what the Operator has created:
```
$ kubectl get all,ingress
Warning: extensions/v1beta1 Ingress is deprecated in v1.14+, unavailable in v1.22+; use networking.k8s.io/v1 Ingress
NAME                            READY   STATUS    RESTARTS   AGE
pod/notebook-675b679485-gnvqv   1/1     Running   0          3m4s

NAME                 TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)    AGE
service/notebook     ClusterIP   10.102.82.29   <none>        8888/TCP   3m4s

NAME                       READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/notebook   1/1     1            1           3m4s

NAME                                  DESIRED   CURRENT   READY   AGE
replicaset.apps/notebook-675b679485   1         1         1       3m4s

NAME                          CLASS    HOSTS                                  ADDRESS        PORTS     AGE
ingress.extensions/notebook   <none>   notebook-default.192.168.49.2.nip.io   192.168.49.2   80        3m4s
```

Access the notebook at the URL listed (including the token). It works!

### Delete the notebook
```
$ kubectl delete jupyternotebooks.squonk.it/notebook
jupyternotebook.squonk.it "notebook" deleted
```


### Delete the CRD
```
$ kubectl delete crd/jupyternotebooks.squonk.it
customresourcedefinition.apiextensions.k8s.io "jupyternotebooks.squonk.it" deleted
```

# Deployment
The container image was created like this:
**Build the container image**
```
docker build -t tdudgeon/jupyter-operator .
```
**Push the container image**
```
docker push tdudgeon/jupyter-operator .
```

## Deploy the operator as a container

Note that this deployment is very basic and assumes you are working in the `default` namespace.

The RBAC settings (the rbac.yaml file), are preliminary. They appear to work but may not cover all options and may be
more permissive than are needed. To apply them run:
```
kubectl create -f rbac.yaml
```
Prior to getting these to work a service account with all privileges granted was created like this:
```
kubectl create sa jupyternotebooks-account
kubectl create clusterrolebinding add-on-cluster-admin --clusterrole=cluster-admin --serviceaccount=default:jupyternotebooks-account
```
This should now not be necessary as using RBAC will be more secure.

Now create the deployment of the operator:
```
kubectl create -f deployment.yaml 
```
Find the pod and look the logs for any errors.
You should see something like this:
```
/usr/local/lib/python3.9/site-packages/kopf/reactor/running.py:168: FutureWarning: Absence of either namespaces or cluster-wide flag will become an error soon. For now, switching to the cluster-wide mode for backward compatibility.
  warnings.warn("Absence of either namespaces or cluster-wide flag will become an error soon."
[2021-03-29 11:45:53,650] kopf.reactor.activit [INFO    ] Initial authentication has been initiated.
[2021-03-29 11:45:53,651] kopf.activities.auth [DEBUG   ] Activity 'login_via_client' is invoked.
[2021-03-29 11:45:53,652] kopf.activities.auth [DEBUG   ] Client is configured in cluster with service account.
[2021-03-29 11:45:53,653] kopf.activities.auth [INFO    ] Activity 'login_via_client' succeeded.
[2021-03-29 11:45:53,653] kopf.reactor.activit [INFO    ] Initial authentication has finished.
[2021-03-29 11:45:54,057] kopf.clients.watchin [DEBUG   ] Starting the watch-stream for customresourcedefinitions.v1.apiextensions.k8s.io cluster-wide.
[2021-03-29 11:45:54,082] kopf.clients.watchin [DEBUG   ] Starting the watch-stream for jupyternotebooks.v1alpha1.squonk.it cluster-wide.
```

Now you can create a notebook like this:
```
kubectl create -f notebook-2.yaml
```

# TODO

Lots of remaining work. In the immediate term:

1. Review the [CRD definintion](crd.yaml) which was hacked together from what the workshop deployment provided. (#2)
1. Review the [RBAC](rbac.yaml) that is need for the ServiceAccount when running the operator container. (#4)
