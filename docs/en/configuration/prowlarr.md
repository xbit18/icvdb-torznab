# Connect Prowlarr

Connect Prowlarr from the WebUI and add Violarr as an indexer.

## The two URLs have opposite directions

The configuration uses two different addresses:

- **Prowlarr URL** is used by **Violarr → Prowlarr**.
- **Indexer URL** is stored in Prowlarr and used by **Prowlarr → Violarr**.

The two services therefore do not necessarily see `localhost` or the same
hostnames in the same way.

### Both applications in Docker on the same network

Normally use:

```text
Prowlarr URL: http://prowlarr:9696
Indexer URL:  http://icvdb-torznab:8000/api
```

### Violarr in Docker and Prowlarr as a Windows service

With Docker Desktop, normally use:

```text
Prowlarr URL: http://host.docker.internal:9696
Indexer URL:  http://localhost:8000/api
```

The first address lets the Violarr container reach the host machine. The second
works because Prowlarr runs on the host and reaches Violarr through published
port `8000`.

On Linux Docker Engine, `host.docker.internal` may require an explicit host
gateway configuration.

## Quick path

1. In Prowlarr, copy the key from **Settings → General → Security → API Key**.
2. Open **Prowlarr** in the Violarr WebUI.
3. Enter the **Prowlarr URL** appropriate for your topology.
4. Enter the **API key**.
5. Enter the **Indexer URL as seen by Prowlarr**.
6. Select **Save Prowlarr settings**, then **Test connection**.
7. When the status is **Connected**, select **Add Violarr to Prowlarr**.

## Error diagnostics

Violarr distinguishes the main integration stages.

- If **Violarr cannot reach Prowlarr**, check the URL, port, firewall, and
  Docker networking.
- If Prowlarr replies with `401` or `403`, check the API key.
- If the indexer test fails after the Prowlarr connection succeeds, the problem
  is normally in the **Prowlarr → Violarr** direction: check the Indexer URL.
- Safe technical details returned by Prowlarr are logged to the browser console
  to make debugging easier.

API keys and tracebacks are not included in details exposed to the WebUI.

## Expected result

- The WebUI shows **Connected**.
- Prowlarr contains an indexer named **Violarr**.
- Adding it again does not create duplicates.

## Change the key

- A saved key remains active until you select **Replace key** or **Clear the
  saved API key**, then save.
- If the test fails, check the URLs, key, and networking in
  [troubleshooting](../troubleshooting).
