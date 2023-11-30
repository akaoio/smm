import frappe
from frappe import _
import requests
import json
import base64
import hashlib
import re
import os
from urllib.parse import urlencode
from . import utils

# READ THIS DOC: https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow

class Facebook:
    def __init__(self, client_id=None, client_secret=None, redirect_uri=None, access_token=None, refresh_token=None, scope=[], authorization_type="Bearer", content_type="json"):
        self.base_url = "https://graph.facebook.com"
        # https://www.facebook.com/v18.0/dialog/oauth?client_id={app-id}&redirect_uri={redirect-uri}&state={state-param}
        self.auth_url = "https://graph.facebook.com/oauth/authorize"
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope or ["tweet.read", "tweet.write", "tweet.moderate.write", "users.read", "follows.read", "follows.write", "offline.access", "space.read",
                               "mute.read", "mute.write", "like.read", "like.write", "list.read", "list.write", "block.read", "block.write", "bookmark.read", "bookmark.write"]
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.authorization_type = authorization_type
        self.content_type = content_type
        self.state = None
        config = frappe.get_site_config() or {}
        domains = config.get("domains") or []
        protocol = "https" if config.get("ssl_certificate") else "http"

        # Check if frappe.local.request.host exists
        host = getattr(getattr(frappe.local, "request", {}), "host", "")
        self.redirect_uri = redirect_uri or ("https://skedew.com/redirect" if host == "localhost:8000" else f"{protocol}://{host or domains[0]}/api/method/smm.libs.facebook.callback")

    def bearer(self):
        return f"Bearer {self.access_token}"

    def basic(self):
        return f"Basic {base64.b64encode(f'{self.client_id}:{self.client_secret}'.encode('utf-8')).decode('utf-8')}"

    def authorization_header(self, type=None):
        type = type or self.authorization_type
        return self.bearer() if type == "Bearer" else self.basic() if type == "Basic" else None

    def content_type_header(self, type=None):
        type = type or self.content_type
        return "application/json" if type == "json" else "application/x-www-form-urlencoded" if type == "urlencoded" else None

    def headers(self, authorization_type=None, content_type=None):
        authorization_type = authorization_type or self.authorization_type
        content_type = content_type or self.content_type
        return {
            "Authorization": self.authorization_header(authorization_type),
            "Content-Type": self.content_type_header(content_type)
        }

    def verifier(self):
        return re.sub("[^a-zA-Z0-9]+", "", base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8"))

    def challenge(self, verifier):
        return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest()).decode("utf-8").replace("=", "")

    def new_state(self):
        self.state = self.verifier()
        return self.state

    def request(self, method="GET", url=None, endpoint=None, params={}, json={}, headers={}, request=True):
        url = url or self.base_url + endpoint

        authorization_type, content_type = headers.get("authorization_type"), headers.get("content_type")

        headers = self.headers(authorization_type, content_type)

        # Complete URL with encoded parameters
        if method == "GET" and not request:
            return url + "?" + urlencode(params)
        if request:
            return requests.request(method, url, params=params, json=json, headers=headers)

    # Returns authorization URL, state, code_verifier, code_challenge, code_challenge_method
    def authorize(self, redirect_uri=None, scope=[], state=None, code_verifier=None, code_challenge=None, code_challenge_method="S256"):
        scope = scope or self.scope
        state = state or self.new_state()
        code_verifier = code_verifier or self.verifier()
        code_challenge = code_challenge or self.challenge(code_verifier)
        code_challenge_method = code_challenge_method or "S256"

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "scope": " ".join(scope),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method
        }

        url = self.request("GET", url=self.auth_url, params=params, request=False)

        return url, state, code_verifier, code_challenge, code_challenge_method

    # Get access token from code
    def token(self, code_verifier=None, code=None, redirect_uri=None):
        if not code_verifier or not code:
            return

        return self.request(
            "POST",
            endpoint="/2/oauth2/token",
            params={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri or self.redirect_uri
            },
            headers={
                "authorization_type": "Basic",
                "content_type": "urlencoded"
            }
        )

    # Refresh access token
    def refresh_access_token(self, token=None):
        token = token or self.refresh_token
        if not token:
            return

        return self.request(
            "POST",
            endpoint="/2/oauth2/token",
            params={
                "grant_type": "refresh_token",
                "refresh_token": token,
            },
            headers={"authorization_type": "Basic",
                     "content_type": "urlencoded"}
        )


@frappe.whitelist()
def authorize(**args):
    unsaved = utils.find(args, "__unsaved")
    name = utils.find(args, "name") if not unsaved else None
    api = utils.find(args, "api")
    if not api:
        frappe.msgprint(_("{0} is empty").format(_("API")))
        return
    doc = frappe.get_doc("API", api)
    client_id = doc.get_password("client_id") or None
    client_secret = doc.get_password("client_secret") or None
    if not client_id or not client_secret:
        frappe.msgprint(_("Client ID or Client Secret or both not found"))
        return

    client = Facebook(client_id)

    url, state, code_verifier, code_challenge, code_challenge_method = client.authorize()

    session_data = {
        "state": state,
        "user": frappe.session.user,
        "API": api,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": code_verifier,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }

    if name:
        session_data["name"] = name

    # Save session data to frappe cache so that it can be used later for verification
    frappe.cache().set_value(state, json.dumps(session_data))

    return {"state": state, "authorization_url": url}


@frappe.whitelist()
def callback(**args):
    error, state, code = args.get("error"), args.get("state"), args.get("code")
    if error:
        redirect_url = "/app/agent"
        frappe.local.response.update({"type": "redirect", "location": redirect_url, "message": _("Redirecting to {0}").format(_("Agent"))})
        return
    if state and code:
        data = frappe.cache().get_value(state)
        if data:
            session = json.loads(data)
            name = session.get("name")
            api = session.get("API")
            doc = frappe.get_doc("API", api)
            client_id = session.get("client_id") or doc.get_password("client_id") or None
            client_secret = session.get("client_secret") or doc.get_password("client_secret") or None
            code_verifier = session.get("code_verifier")
            client = Facebook(client_id, client_secret)

            response = client.token(code_verifier=code_verifier, code=code)

            if response.status_code == 200:
                response = response.json()
                if "access_token" not in response:
                    frappe.throw("Access token not received. Authorization failed.")

                tokens = {
                    "access_token": response.get("access_token"),
                    "refresh_token": response.get("refresh_token")
                }

                if name:
                    doc = frappe.get_doc("Agent", name)
                    doc.update(tokens)
                    doc.save()
                else:
                    doc = frappe.get_doc({
                        "doctype": "Agent",
                        "api": api,
                        **tokens
                    })
                    doc.insert()

                frappe.db.commit()

                # Get user profile after successful authorization
                profile(name=doc.name)

                redirect_url = f"/app/agent/{doc.name}"
                frappe.local.response.update({"type": "redirect", "location": redirect_url, "message": _("Redirecting to {0} {1}").format(_("Agent"), doc.name)})

        # Delete frappe cache to release memory
        frappe.cache().delete_value(state)
    return args


@frappe.whitelist()
def refresh_access_token(**args):
    name = utils.find(args, "name")
    if not name:
        frappe.msgprint(_("{0} name is empty").format(_("Agent")))
        return

    doc = frappe.get_doc("Agent", name)
    token = doc.get_password("refresh_token") or None
    api = doc.get("api")
    doc = frappe.get_doc("API", api)
    client_id = doc.get_password("client_id") or None
    client_secret = doc.get_password("client_secret") or None

    if not client_id or not client_secret:
        frappe.msgprint(_("Client ID or Client Secret or both not found"))
        return

    client = Facebook(client_id, client_secret)

    response = client.refresh_access_token(token)

    if response.status_code == 200:
        response = response.json()
        access_token, refresh_token = response.get("access_token"), response.get("refresh_token")
        frappe.get_doc("Agent", name).update({"access_token": access_token, "refresh_token": refresh_token}).save()
        frappe.db.commit()

    return token


@frappe.whitelist()
def profile(**args):
    name = utils.find(args, "name")
    doc = frappe.get_doc("Agent", name)
    token = doc.get_password("access_token") or None

    client = Facebook(access_token=token)
    response = client.request(
        "GET",
        endpoint="/2/users/me",
        params={"user.fields": "created_at,description,entities,id,location,name,pinned_tweet_id,profile_image_url,protected,public_metrics,url,username,verified,verified_type,withheld"},
        headers={"authorization_type": "Bearer", "content_type": "json"}
    )

    profile = response.json().get("data")
    
    audience_size = doc.get("audience_size")
    if profile.get("public_metrics"):
        public_metrics = profile.get("public_metrics") or {}
        audience_size = public_metrics.get("followers_count") if public_metrics.get("followers_count") else None
    
    frappe.get_doc("Agent", name).update({"uid": profile.get("id"), "display_name": profile.get("name"), "alias": profile.get("username"), "description": profile.get("description"), "picture": profile.get("profile_image_url"), "audience_size": audience_size}).save()

    frappe.db.commit()

    return response


@frappe.whitelist()
def send(**args):
    name = utils.find(args, "name")
    agent = utils.find(args, "agent") or frappe.get_doc("Agent", name)
    text = utils.find(args, "text")
    token = agent.get_password("access_token") or None
    client = Facebook(access_token=token)

    linked_external_id = utils.find(args, "linked_external_id")

    params = {"text": text}
    if linked_external_id:
        params.update({
            "reply": {
                "in_reply_to_tweet_id": linked_external_id
            }
        })

    response = client.request(
        "POST",
        endpoint="/2/tweets",
        json=params,
        headers={"authorization_type": "Bearer", "content_type": "json"}
    )

    return response