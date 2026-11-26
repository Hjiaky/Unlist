# Optional language model

**Unlist is complete without a language model (an "LLM").** It is off unless you switch it on, and nothing in the core loop needs it. Every job has a plain fallback that works without one.

When it is on, a language model helps with four small jobs. What it says is always a **suggestion**, marked with where it came from. It changes nothing and sends nothing until you press the button that applies it, and every email still waits for your approval.

## Recommended: a local, free model

Run a model on your own machine or network. Then nothing leaves your network. Free options include [Ollama](https://ollama.com/) and the server of [llama.cpp](https://github.com/ggml-org/llama.cpp). Both offer an OpenAI-compatible address, which is all Unlist needs.

Example with Ollama on the same machine as Unlist:

```sh
ollama pull llama3.1        # downloads the model; "ollama run llama3.1" also downloads it and opens a chat
```

Then, on Unlist's language model settings page (`/llm/`):

- **Endpoint address:** `http://<host>:11434/v1`
- **Model name:** `llama3.1`
- Tick "Use the LLM", leave "Local or remote" on "Detect from the address", and save.

`llama3.1` is only the example the app's own help uses. Any model Ollama offers works; larger ones give better suggestions and need more memory. For llama.cpp's server the address is typically `http://localhost:8080/v1`. A local model needs no API key.

### If Unlist runs in Docker

Inside the container, `localhost` is the container itself, not your machine. To reach Ollama running on the **host machine**, use the host name `host.docker.internal`.

- On **Docker Desktop** (macOS and Windows) the name works as it is.
- On **Linux**, add this to the `unlist` service in `compose.yaml`:

  ```yaml
      extra_hosts:
        - "host.docker.internal:host-gateway"
  ```

  and restart with `docker compose up -d`. The endpoint address is then `http://host.docker.internal:11434/v1`.

- Ollama by default listens only on the host's own loopback address, which a container cannot reach through `host-gateway`. Make Ollama listen on more addresses (its documented setting is the environment variable `OLLAMA_HOST=0.0.0.0`), and **make sure that port is not open to the internet**, because Ollama has no login.

Alternatively, run Ollama as a second container on the same Docker network and use its container name, for example `http://ollama:11434/v1`. Unlist treats a single-word name like this as local. This adds a service to run, which is why the default setup does not do it.

The `host-gateway` syntax is Docker's documented compose form; this guide could not run Docker here to test it end to end.

## The four jobs and what each one sends

This is the list Unlist itself shows on the settings page and in the remote notice:

| Job | What it sends |
|---|---|
| **Sort leftover discovery mail** | Only when you click "Ask the LLM" on a sender the rules left unsorted: the sender's name and domain, and one subject line in which the Subject's name, email addresses and identifying details are replaced by placeholders. |
| **Adapt a draft to another language** | Only when you click "Adapt to …" on a draft: its subject line and text, with the Subject's name, email addresses, identifying details and the reference code replaced by placeholders, and the name of the language. |
| **Suggest reply outcomes** | For every reply Unlist takes in: the new text of the reply (without the quoted original), with the Subject's name, email addresses and identifying details replaced by placeholders. Not the sender, the subject line or any attachment. |
| **Find a privacy contact** | Only when you click "Find privacy contact": the text of the public privacy-policy page whose address you paste. Unlist fetches the page itself. |

Every request also carries the model name and Unlist's fixed instructions for the job.

Without a language model: the rules sort discovery mail, drafts use the English template, keyword rules suggest reply outcomes, and you type the privacy contact in yourself.

Note the third job: with a language model switched on, **every reply** is sent to it, with personal details replaced by placeholders. That is more than the other jobs, which run only when you click. If you use a remote endpoint, think about whether you are comfortable with that.

Placeholders reduce what is revealed, but a reply can still contain other personal text. A local model avoids the question.

## Remote endpoints are nonfree services

Any OpenAI-compatible endpoint works, including a cloud provider's. **A remote endpoint is someone else's service. It receives the data listed above, and its software is not free.** Unlist labels it that way, and marks every suggestion from it "Suggested by <host>, a remote, nonfree service".

"Remote" is decided from the address. These count as **local**: `localhost`, loopback addresses, private network ranges (10.x, 172.16–31.x, 192.168.x, and IPv6 unique local addresses), names ending in `.local`, `.lan`, `.internal` or `.home.arpa`, and single-word names. Everything else counts as remote. You can override this on the settings page (for example, if you reach your own model through a public name).

### The one-time notice

The first time you point Unlist at a remote host, it will **not use it** until you read a notice listing exactly what will be sent (the table above) and press the accept button. After that it asks no more. If you change to a different host, it asks again. If the host really is yours, set "Local or remote" to "Local" instead.

The API key, if you enter one, is stored **encrypted** with the instance's [key](install.md#the-key). "Forget the stored API key" removes it.

## Switching it off

Untick "Use the LLM" and save. Nothing more is sent. The settings stay, so you can switch it on later.
