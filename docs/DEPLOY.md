# EBE Command · Deploy the hosted SaaS

Goal: put the multi-tenant `host` server on a cheap always-on box so real venues can log
in at a domain and pay you monthly. ~30 minutes, ~$5–6/mo. Pure stdlib — no Docker, no
Postgres, no build step.

---

## ⭐ Fastest path: Cloudflare Tunnel (you already have a Cloudflare domain)

If your domain is on Cloudflare, this is **$0, no VPS, no port-forwarding, automatic HTTPS** —
EBE runs on your own PC and Cloudflare gives clients a clean `https://ebe.yourdomain.com`.

1. **Run EBE locally** (one terminal, leave it open):
   ```powershell
   cd $HOME\ebe-commerce
   $env:EBE_HOST_SECRET="some-long-random-string"
   $env:EBE_OWNER_PASSWORD="your-owner-password"
   python -m ebe host --port 8080
   ```
2. **Install cloudflared** (Cloudflare's tunnel tool): https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ (Windows installer).
3. **Authenticate + create the tunnel** (second terminal):
   ```powershell
   cloudflared tunnel login                         # opens browser → pick your domain
   cloudflared tunnel create ebe
   cloudflared tunnel route dns ebe ebe.yourdomain.com
   ```
4. **Run the tunnel** pointing at EBE:
   ```powershell
   cloudflared tunnel run --url http://localhost:8080 ebe
   ```
   Now `https://ebe.yourdomain.com/login` is live, encrypted, on your existing domain — free.

> Want it always-on without keeping terminals open? Install both EBE and cloudflared as
> services (`cloudflared service install`), or move to the VPS path below so it runs when
> your PC is off. The tunnel works the same pointing at a VPS.

Onboard a client (from the PC running EBE, or the `/admin` panel):
```powershell
python -m ebe tenant --issue cloud9 --id THEIR_PASSWORD --days 30
```

---

## Hands-off billing + self-serve signup (Stripe)

Make EBE sell itself: venues sign up at `/signup`, pay via Stripe, and get activated
automatically. Renewals auto-extend; failed payments auto-suspend. No manual `tenant --issue`.

1. **In Stripe:** create a subscription **Product** (e.g. "EBE · $99/mo") → make a
   **Payment Link** for it. Copy the link URL.
2. **In Stripe → Developers → Webhooks:** add an endpoint
   `https://ebe.ebehq.com/webhook/stripe`, subscribe to:
   `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`,
   `customer.subscription.deleted`. Copy the signing secret (`whsec_…`).
3. **Set these env vars** (in the systemd unit, or your PowerShell session):
   ```
   EBE_CHECKOUT_URL=https://buy.stripe.com/your_payment_link
   EBE_STRIPE_WEBHOOK_SECRET=whsec_xxx
   EBE_TRIAL_DAYS=0          # or e.g. 14 for a free trial before payment
   ```
4. Done. Flow: venue → `/signup` → Stripe checkout → pays → webhook activates them →
   monthly invoice auto-renews → missed payment auto-suspends (locked server-side).

> The Payment Link carries `client_reference_id` = the tenant's login ID, so the webhook
> knows exactly who paid. Test it with Stripe's test mode + the webhook "Send test event".

---

## Always-on path: a $5/mo VPS

(Use this when you don't want EBE tied to your PC being on. You can still front it with the
same Cloudflare Tunnel, or use nginx + certbot as below.)

---


## 1. Get a server (~$5/mo)
Pick one, create an **Ubuntu 24.04** droplet/instance (smallest tier is plenty):
- **DigitalOcean** ($6/mo) · **Hetzner** (€4/mo, cheapest) · **Linode/Vultr** ($5/mo)

Note the server's **public IP**.

## 2. Point a domain at it
In your domain registrar (Namecheap/Cloudflare/GoDaddy), add an **A record**:
`ebe.yourdomain.com  →  <server IP>`. (No domain yet? You can test with the raw IP first.)

## 3. Put EBE on the server
SSH in (`ssh root@<IP>`), then:
```bash
apt update && apt install -y python3 git nginx
adduser --system --group ebe
git clone <your repo>  /opt/ebe-commerce      # or scp your folder to /opt/ebe-commerce
chown -R ebe:ebe /opt/ebe-commerce
```
(Repo private? Use a GitHub deploy token, or `scp -r` the folder up from your PC.)

## 4. Run it as an always-on service
```bash
cp /opt/ebe-commerce/deploy/ebe-host.service /etc/systemd/system/ebe-host.service
# edit the two secrets:
nano /etc/systemd/system/ebe-host.service     # set EBE_HOST_SECRET + EBE_OWNER_PASSWORD
systemctl daemon-reload
systemctl enable --now ebe-host
systemctl status ebe-host                      # should say active (running)
curl localhost:8080/health                     # -> ok
```
It now restarts on crash and on reboot, automatically.

## 5. Put it behind a domain + HTTPS
```bash
cp /opt/ebe-commerce/deploy/nginx-ebe.conf /etc/nginx/sites-available/ebe
nano /etc/nginx/sites-available/ebe            # set server_name ebe.yourdomain.com
ln -s /etc/nginx/sites-available/ebe /etc/nginx/sites-enabled/ebe
nginx -t && systemctl reload nginx
# free auto-renewing TLS:
apt install -y certbot python3-certbot-nginx
certbot --nginx -d ebe.yourdomain.com
```
Now `https://ebe.yourdomain.com` is live and encrypted.

## 6. Open the firewall
```bash
ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw --force enable
```
(Port 8080 stays internal — only nginx talks to it.)

## 7. Onboard your first paying client
From the server (or the /admin web panel at `https://ebe.yourdomain.com/admin`):
```bash
cd /opt/ebe-commerce
python3 -m ebe tenant --issue cloud9 --id THEIR_PASSWORD --days 30
```
Give them `https://ebe.yourdomain.com/login` + their ID/password. When they pay each month:
```bash
python3 -m ebe tenant --issue cloud9 --days 30      # renew
```
Miss a payment → it lapses (or `python3 -m ebe tenant` → suspend in /admin) → they're locked out, **enforced on the server**.

---

## Operating notes
- **Backups:** the whole business is in `/opt/ebe-commerce/ebe_tenants.db` + `/opt/ebe-commerce/tenants/`. Back those up (a nightly `cp` to object storage or `cron` + `rclone`).
- **Updates:** `cd /opt/ebe-commerce && git pull && systemctl restart ebe-host`.
- **Logs:** `journalctl -u ebe-host -f`.
- **Scaling:** the threaded stdlib server handles dozens of venues fine. If you grow past that, front it with more workers or move tenants to Postgres — but you're a long way from needing that.

That's it — EBE is now a real subscription business other operators log into and pay for.
