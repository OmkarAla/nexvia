# Kubernetes deployment evidence

Date: 2026-11-21
Cluster: kind v0.33.0, node v1.37.0 (single control-plane)
Images: nexvia-fraud:dev, nexvia-fraud-dashboard:dev (loaded into kind)

## Nodes
```
NAME                   STATUS   ROLES           AGE   VERSION
nexvia-control-plane   Ready    control-plane   39m   v1.37.0
```

## Pods
```
NAME                            READY   STATUS      RESTARTS   AGE     IP            NODE                   NOMINATED NODE   READINESS GATES
api-5db45db9b7-kjf7k            1/1     Running     0          2m31s   10.244.0.37   nexvia-control-plane   <none>           <none>
consumer-66d5c856d7-fv4zq       1/1     Running     0          2m31s   10.244.0.36   nexvia-control-plane   <none>           <none>
dashboard-767684c84f-sknjj      1/1     Running     0          45s     10.244.0.38   nexvia-control-plane   <none>           <none>
drift-monitor-f8958dc88-hmrc5   1/1     Running     0          14m     10.244.0.31   nexvia-control-plane   <none>           <none>
feast-materialize-8vfxq         0/1     Completed   0          2m59s   10.244.0.35   nexvia-control-plane   <none>           <none>
kafka-65cdf844bc-9xclz          1/1     Running     0          21m     10.244.0.25   nexvia-control-plane   <none>           <none>
postgres-7bb8bcdb74-pksnm       1/1     Running     0          37m     10.244.0.13   nexvia-control-plane   <none>           <none>
producer-6bf7b8bb97-nfnwt       1/1     Running     0          37m     10.244.0.9    nexvia-control-plane   <none>           <none>
redis-56898d8dd7-pmk7c          1/1     Running     0          37m     10.244.0.10   nexvia-control-plane   <none>           <none>
seed-cdgjh                      0/1     Completed   0          37m     10.244.0.12   nexvia-control-plane   <none>           <none>
```

## Jobs
```
NAME                STATUS     COMPLETIONS   DURATION   AGE
feast-materialize   Complete   1/1           17s        3m
seed                Complete   1/1           10m        37m
```

## Services
```
NAME        TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)             AGE
api         ClusterIP   10.96.11.209    <none>        8000/TCP            37m
dashboard   ClusterIP   10.96.29.97     <none>        80/TCP              37m
kafka       ClusterIP   None            <none>        9092/TCP,9093/TCP   21m
postgres    ClusterIP   10.96.187.93    <none>        5432/TCP            37m
redis       ClusterIP   10.96.161.189   <none>        6379/TCP            37m
```

## API check (port-forward 8081)
```
{"status":"ok","model_version":"demo-002-feast"}
```

## Dashboard

Screenshot: `docs/screenshots/k8s-dashboard.png` (100 open alerts, model demo-002-feast).

## Notes

- Kafka runs KRaft with the controller quorum on `localhost:9093` and a headless service (`publishNotReadyAddresses: true`) so readiness does not deadlock on an empty endpoint list.
- `feast-materialize` completed and populated the shared `feast-data` PVC; API and consumer restarted afterwards.
- The dashboard image in this run was built with `VITE_API_URL=http://localhost:8081` to avoid the host demo on port 8000; the default build arg is `http://localhost:8000`.
