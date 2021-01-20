# Jupyter Operator

This repo is an experiment to create a simple Kubernetes (K8S) Operator that can be used to create
Jupyter Notebooks within  a K8S cluster. It is heavily basede on work from @GrapahmDumpleton that 
can be found [here](https://github.com/jupyter-on-kubernetes/lab-jupyter-on-k8s-02). That involves
running an operator within his [EduKates](https://github.com/eduk8s/eduk8s) environment already 
running in the cluster.

What this repo is trying to do is pull out only what is essential for deploying ONLY the Jupyter operator
to the cluster.

**NOTE** this work is preliminary and far from fully functional.

## My environment

Minukube  with these addons enabled:
* default-storageclass
* ingress
* ingress-dns
* storage-provisioner

Python 3.9.1 with kopf and kubernetes installed with Pip.
I use a Conda environment.

## Deployment of the Operator

### Deploy the CRD

```
$ kubectl create -f crd.yaml
```

### Run the operator

For testing the operator is run manually from Python.
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

This corresponds to notebook-2 in the jupyter-on-kubernetes/lab-jupyter-on-k8s-02 repo.
It deploys a very basic notbook environment.

Check what has been created:
```
$ kubectl get jupyternotebooks.jupyter-on-kubernetes.test
NAME       URL   PASSWORD
notebook         
```
Note that the URL and PASSWORD fields are not filled, but the notebook CRD is present.

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

Access the notebook at http://notebook-default.192.168.49.2.nip.io. When the page opens use the password
shown in the kopf logs. It works!

### Delete the notebook
```
$ kubectl delete jupyternotebooks.jupyter-on-kubernetes.test/notebook
jupyternotebook.jupyter-on-kubernetes.test "notebook" deleted
```


### Delete the CRD
```
$ kubectl delete crd/jupyternotebooks.jupyter-on-kubernetes.test
customresourcedefinition.apiextensions.k8s.io "jupyternotebooks.jupyter-on-kubernetes.test" deleted
```

# TODO

Lots of remaining work. In the immediate term:

1. Figure out why the URL and PASSWORD fields are not filled in the output of the CRD. (#1)
2. Review the [CRD definintion](crd.yaml) which was hacked together from what the workshop deployment provided. (#2)
3. Build container for the operator.
4. Determine what RBAC is need for the ServiceAccount when running the operator container.

