# Cloud DB HA 연결 방식

- Cloud DB for MySQL은 Master/Standby로 HA 구성.
- Failover 시 Master IP가 바뀔 수 있으므로, 앱은 고정 사설 IP가 아니라 Private 도메인(Endpoint)로 연결.
- DB_HOST: db-3p6i9a.vpc-cdb.ntruss.com
- DB_NAME: mydb-002 (권한 이슈로 service_db 대신 기본 DB에 이관)
