# Like endpoint authentication

Both `/like` and `/likeff` require the header `X-API-Key`. Set the same
`LIKE_API_KEY` secret in the API and Telegram bot environments or their `.env`
files. A random secret has been added to the local `.env`; keep it private.
Configure the hosting environment separately and restart the API and bots.

```http
GET /likeff?uid=123456
X-API-Key: YOUR_SECRET
```

The bot adds this header automatically for both endpoints. Missing or wrong
keys return HTTP 401 before region lookup, slot allocation or sending likes.
An unconfigured API returns HTTP 503 and accepts no like requests. Passwords
in query parameters are not accepted. Other endpoints retain their current
authentication behavior.

Use HTTPS for network access: HTTP does not encrypt the secret. To rotate it,
replace `LIKE_API_KEY` in both service environments and restart them. Do not
commit `.env` or include the key in URLs or logs.
