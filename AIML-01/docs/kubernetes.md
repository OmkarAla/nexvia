# Kubernetes

The fraud stack ships as Kustomize manifests for a single-node cluster (kind or Docker Desktop Kubernetes). Compose remains the primary demo path.

## Layout

```
k8s/
  base/            namespace, config, deployments, services, seed Job
  overlays/kind/   image names for a local kind cluster
```

## Build and load images

```bash
docker build -t nexvia-fraud:dev .
docker build -t nexvia-fraud-dashboard:dev ./dashboard

kind create cluster --name nexvia
kind load docker-image nexvia-fraud:dev --name nexvia
kind load docker-image nexvia-fraud-dashboard:dev --name nexvia
```

Docker Desktop Kubernetes can use the local images directly without `kind load`.

## Apply

```bash
kubectl apply -k k8s/overlays/kind
kubectl -n nexvia wait --for=condition=complete job/seed --timeout=180s
kubectl -n nexvia get pods
```

Then forward the two services:

```bash
kubectl -n nexvia port-forward svc/api 8000:8000
kubectl -n nexvia port-forward svc/dashboard 8080:80
```

- Dashboard: <http://localhost:8080>
- API: <http://localhost:8000/docs>

The dashboard image is built with `VITE_API_URL=http://localhost:8000`, matching the port-forward.

## What runs

| Workload | Kind | Notes |
|---|---|---|
| `postgres` | Deployment + PVC | 1 Gi volume |
| `kafka` | Deployment | apache/kafka 3.7.1, KRaft, in-cluster listener `kafka:9092` |
| `redis` | Deployment | reserved for the Feast online store |
| `api` | Deployment + Service | readiness/liveness on `/health` |
| `consumer` | Deployment | waits for Kafka with `nc` |
| `producer` | Deployment | replays at 2/s |
| `drift-monitor` | Deployment | 60 s loop |
| `dashboard` | Deployment + Service | nginx |
| `seed` | Job | 600 rows, waits for Postgres |

## Validation

```bash
kubectl kustomize k8s/overlays/kind > /dev/null
python -m pytest tests/test_k8s.py -q
```

`kubectl kustomize` validates structure without a cluster. The test asserts every workload and image is present.

## Cautions

- The demo Secret contains literal credentials. Do not reuse these manifests outside a local cluster.
- Kafka and Postgres are single replicas with no replication or backups.
- There is no Ingress, TLS, or auth. Use port-forwarding only.
- `kind` is not installed on the current development machine; manifests are validated statically, not applied.
