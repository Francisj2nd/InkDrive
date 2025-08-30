# Render Configuration for Subdomain Support

To make the subdomain routing for `studio.inkdrive.ink` work correctly on your Render-hosted application, you need to make two important changes in your Render dashboard.

These changes ensure that the Flask application is aware of its domain and can share login sessions securely between the main domain and the studio subdomain.

---

## 1. Add Custom Domains

You need to add both your main domain and your new subdomain to your Render service.

1.  Go to your service's dashboard on Render.
2.  Navigate to the **"Settings"** tab.
3.  Scroll down to the **"Custom Domains"** section.
4.  Add `inkdrive.ink` as a custom domain and follow the instructions to configure your DNS provider.
5.  Add `studio.inkdrive.ink` as another custom domain and follow the DNS configuration instructions for it as well.

After this step, Render will be able to receive traffic for both domains and route it to your application.

---

## 2. Set Environment Variables

The application code now requires two new environment variables to handle the routing and session logic.

1.  Go to your service's dashboard on Render.
2.  Navigate to the **"Environment"** tab.
3.  Under the **"Environment Variables"** section, click **"Add Environment Variable"** twice to add the following two variables:

| Key                     | Value          |
| ----------------------- | -------------- |
| `SERVER_NAME`           | `inkdrive.ink` |
| `SESSION_COOKIE_DOMAIN` | `.inkdrive.ink`|

**Important Notes:**
*   Make sure there are no typos in the keys.
*   For `SESSION_COOKIE_DOMAIN`, the leading dot (`.`) is **essential**. Do not forget it.
*   The `SERVER_NAME` should **not** include `https://` or any slashes.

---

After completing these two steps, your application should be fully configured to handle the subdomain logic as required. You may need to trigger a new deployment for the environment variables to be applied.
