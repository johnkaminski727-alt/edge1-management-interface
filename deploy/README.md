# Deployment Notes

Target repo path recommendation:

`/opt/edge1-management-interface`

Initial deployment should be source-only. Do not expose the website publicly.

Required deployment properties:

- private/VPN-only
- authenticated operator access
- read-only first
- no secrets committed to git
- no binary archive files committed to git

