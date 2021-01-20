import os
import random
import hashlib
import string

import kopf
import pykube

api = pykube.HTTPClient(pykube.KubeConfig.from_env())

notebook_startup = """#!/bin/bash
conda init

source $HOME/.bashrc

if [ ! -f $HOME/.condarc ]; then
    cat > $HOME/.condarc << EOF
envs_dirs:
  - $HOME/.conda/envs
EOF
fi

if [ -d $HOME/.conda/envs/workspace ]; then
    echo "Activate virtual environment 'workspace'."
    conda activate workspace
fi

if [ ! -f $HOME/.jupyter/jupyter_notebook_config.json ]; then
    mkdir -p $HOME/.jupyter
    cat > $HOME/.jupyter/jupyter_notebook_config.json << EOF
{
  "NotebookApp": {
    "password": "%(password_hash)s"
  }
}
EOF
fi
"""

@kopf.on.create("jupyter-on-kubernetes.test", "v1alpha1", "jupyternotebooks", id="jupyter")
def create(name, uid, namespace, spec, logger, **_):
    algorithm = "sha1"
    salt_len = 12

    characters = string.ascii_letters + string.digits
    password = "".join(random.sample(characters, 16))

    h = hashlib.new(algorithm)
    salt = ("%0" + str(salt_len) + "x") % random.getrandbits(4 * salt_len)
    h.update(bytes(password, "utf-8") + salt.encode("ascii"))

    password_hash = ":".join((algorithm, salt, h.hexdigest()))

    config_map_body = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "app": name
            }
        },
        "data": {
            "setup-environment.sh": notebook_startup % dict(password_hash=password_hash)
        }
    }

    kopf.adopt(config_map_body)

    K8SConfigMap = pykube.object_factory(api, "v1", "ConfigMap")
    config_map_resource = K8SConfigMap(api, config_map_body)
    config_map_resource.create()

    notebook_interface = spec.get("notebook", {}).get("interface", "lab")

    image = spec.get("deployment", {}).get("image", "jupyter/minimal-notebook:latest")
    service_account = spec.get("deployment", {}).get("serviceAccountName", "default")

    memory_limit = spec.get("deployment", {}).get("resources", {}).get("limits", {}).get("memory", "512Mi")
    memory_request = spec.get("deployment", {}).get("resources", {}).get("requests", {}).get("memory", memory_limit)

    deployment_body = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "app": name
            }
        },
        "spec": {
            "replicas": 1,
            "selector": {
                "matchLabels": {
                    "deployment": name
                }
            },
            "strategy": {
                "type": "Recreate"
            },
            "template": {
                "metadata": {
                    "labels": {
                        "deployment": name
                    }
                },
                "spec": {
                    "serviceAccountName": service_account,
                    "containers": [
                        {
                            "name": "notebook",
                            "image": image,
                            "imagePullPolicy": "Always",
                            "resources": {
                                "requests": {
                                    "memory": memory_request
                                },
                                "limits": {
                                    "memory": memory_limit
                                }
                            },
                            "ports": [
                                {
                                    "name": "8888-tcp",
                                    "containerPort": 8888,
                                    "protocol": "TCP",
                                }
                            ],
                            "env": [],
                            "volumeMounts": [
                                {
                                    "name": "startup",
                                    "mountPath": "/usr/local/bin/before-notebook.d"
                                }
                            ]
                        }
                    ],
                    "securityContext": {
                        "fsGroup": 0
                    },
                    "volumes": [
                        {
                            "name": "startup",
                            "configMap": {
                                "name": "notebook"
                            }
                        }
                    ]
                },
            },
        },
    }

    if notebook_interface != "classic":
        deployment_body["spec"]["template"]["spec"]["containers"][0]["env"].append(
                {"name": "JUPYTER_ENABLE_LAB", "value": "true"})

    storage_request = ""
    storage_limit = ""

    storage_claim_name = spec.get("storage", {}).get("claimName", "")
    storage_sub_path = spec.get("storage", {}).get("claimName", "")

    if not storage_claim_name:
        storage_request = spec.get("deployment", {}).get("resources", {}).get("requests", {}).get("storage", "")
        storage_limit = spec.get("deployment", {}).get("resources", {}).get("limits", {}).get("storage", "")

        if storage_request or storage_limit:
            volume = {"name": "data", "persistentVolumeClaim": {"claimName": "notebook"}}
            deployment_body["spec"]["template"]["spec"]["volumes"].append(volume)

            storage_mount = {"name": "data", "mountPath": "/home/jovyan"}
            deployment_body["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append(storage_mount)

            persistent_volume_claim_body = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "labels": {
                        "app": name
                    }
                },
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {
                        "requests": {},
                        "limits": {}
                    }
                }
            }

            if storage_request:
                persistent_volume_claim_body["spec"]["resources"]["requests"]["storage"] = storage_request

            if storage_limit:
                persistent_volume_claim_body["spec"]["resources"]["limits"]["storage"] = storage_limit
            kopf.adopt(persistent_volume_claim_body)

            K8SPersistentVolumeClaim = pykube.object_factory(api, "v1", "PersistentVolumeClaim")
            persistent_volume_claim_resource = K8SPersistentVolumeClaim(api, persistent_volume_claim_body)
            persistent_volume_claim_resource.create()

    else:
        volume = {"name": "data", "persistentVolumeClaim": {"claimName": storage_claim_name}}
        deployment_body["spec"]["template"]["spec"]["volumes"].append(volume)

        storage_mount = {"name": "data", "mountPath": "/home/jovyan", "subPath": storage_sub_path}
        deployment_body["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append(storage_mount)

    kopf.adopt(deployment_body)

    K8SDeployment = pykube.object_factory(api, "apps/v1", "Deployment")
    deployment_resource = K8SDeployment(api, deployment_body)
    deployment_resource.create()

    service_body = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "app": name
            }
        },
        "spec": {
            "type": "ClusterIP",
            "ports": [
                {
                    "name": "8888-tcp",
                    "port": 8888,
                    "protocol": "TCP",
                    "targetPort": 8888,
                }
            ],
            "selector": {
                "deployment": name
            },
        },
    }

    kopf.adopt(service_body)

    K8SService = pykube.object_factory(api, "v1", "Service")
    service_resource = K8SService(api, service_body)
    service_resource.create()

    ingress_domain = os.environ.get("INGRESS_DOMAIN")
    ingress_hostname = f"notebook-{namespace}.{ingress_domain}"

    ingress_body = {
        "apiVersion": "extensions/v1beta1",
        "kind": "Ingress",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "app": name
            },
            "annotations": {
                "projectcontour.io/websocket-routes": "/"
            }
        },
        "spec": {
            "rules": [
                {
                    "host": ingress_hostname,
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "backend": {
                                    "serviceName": name,
                                    "servicePort": 8888,
                                },
                            }
                        ]
                    }
                }
            ]
        }
    }

    kopf.adopt(ingress_body)

    K8SIngress = pykube.object_factory(api, "extensions/v1beta1", "Ingress")
    ingress_resource = K8SIngress(api, ingress_body)
    ingress_resource.create()

    return {
        "notebook" : {
            "url": f"http://{ingress_hostname}",
            "password": password,
            "interface": notebook_interface,
        },
        "deployment": {
            "image": image,
            "serviceAccountName": service_account,
            "resources": {
                "requests": {
                    "memory": memory_request,
                    "storage": storage_request
                },
                "limits": {
                    "memory": memory_limit,
                    "storage": storage_limit
                }
            }
        },
        "storage": {
            "claimName": storage_claim_name,
            "subPath": storage_sub_path
        }
    }
