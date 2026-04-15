# Runbook

## Environment
Set:
- `AWS_PROFILE`
- `AWS_REGION`

## First-pass flow
1. `make bootstrap`
2. `make tf-init`
3. `make tf-plan`
4. `make tf-apply`
5. `make seed`
6. `make query q="sample question"`
7. `make tf-destroy`

## Notes
- Cheap first pass targets small RDS PostgreSQL
- Stop or destroy resources when idle
