# A3. Visibility Tier Access Matrix (referenced by FR-16, FR-14, FR-15)

| Requester | `Public` Mini-App | `Need-Auth` Mini-App | `Private` Mini-App |
|-----------|-------------------|----------------------|---------------------|
| Anonymous | 401 | 401 | 401 |
| Same Tenant, different Department | 200 (read) | 403 | 403 |
| Same Tenant, same Department, not whitelisted | 200 (read) | 200 | 403 |
| Same Tenant, same Department, whitelisted | 200 | 200 | 200 |
| Cross-Tenant | 404 | 404 | 404 |

404 (not 403) on cross-Tenant access is intentional — never confirm a Mini-App's existence to a caller outside its Tenant.
