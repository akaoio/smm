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

# Facebook Graph API integration for posting content
# Docs: https://developers.facebook.com/docs/graph-api/
# Pages API: https://developers.facebook.com/docs/pages-api/

class Facebook:
    def __init__(self, client_id=None, client_secret=None, redirect_uri=None, access_token=None, refresh_token=None, scope=[], authorization_type="Bearer", content_type="json"):
        self.base_url = "https://graph.facebook.com"
        self.auth_url = "https://www.facebook.com/v18.0/dialog/oauth"
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope or ["public_profile", "email", "pages_show_list", "pages_manage_posts", "pages_manage_engagement", "pages_read_engagement", "publish_to_groups", "publish_video"]
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.authorization_type = authorization_type
        self.content_type = content_type
        self.state = None
        # Use Frappe's proper API to get site URL
        from frappe.utils import get_url
        try:
            # Get base site URL and construct callback
            site_url = get_url().rstrip("//")
            self.redirect_uri = redirect_uri or f"{site_url}/api/method/smm.libs.facebook.callback"
        except:
            # Fallback to request host if get_url() fails
            config = frappe.get_site_config() or {}
            protocol = "https" if config.get("ssl_certificate") else "http"
            host = getattr(getattr(frappe.local, "request", {}), "host", "localhost")
            self.redirect_uri = redirect_uri or f"{protocol}://{host}/api/method/smm.libs.facebook.callback"

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
        return re.sub("[^a-zA-Z0-9]+", "", base64.urlsafe_b64encode(os.urandom(64)).decode("utf-8"))

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
            "scope": ",".join(scope),
            "state": state
        }

        url = self.request("GET", url=self.auth_url, params=params, request=False)

        return url, state, code_verifier, code_challenge, code_challenge_method

    # Get access token from code
    def token(self, code_verifier=None, code=None, redirect_uri=None):
        if not code:
            return

        return self.request(
            "POST",
            endpoint="/v18.0/oauth/access_token",
            params={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri or self.redirect_uri
            }
        )

    # Exchange short-lived token for long-lived token
    def exchange_long_lived_token(self, short_token=None):
        token = short_token or self.access_token
        if not token:
            return

        return self.request(
            "GET",
            endpoint="/v18.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "fb_exchange_token": token
            }
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
    token = doc.get_password("access_token")
    api_doc = frappe.get_doc("API", doc.api)
    client_id = api_doc.get_password("client_id")
    client_secret = api_doc.get_password("client_secret")

    if not client_id or not client_secret or not token:
        frappe.msgprint(_("Missing credentials for token refresh"))
        return

    client = Facebook(client_id=client_id, client_secret=client_secret)
    
    # Exchange for long-lived token (Facebook tokens expire in 60 days)
    response = client.exchange_long_lived_token(token)
    
    if response and response.status_code == 200:
        response_data = response.json()
        new_token = response_data.get("access_token")
        if new_token:
            doc.set_password("access_token", new_token)
            doc.save()
            frappe.db.commit()
            
            # Also refresh page token if exists
            if doc.get_password("page_access_token"):
                profile(name=name)  # Re-fetch page tokens

    return response


@frappe.whitelist()
def profile(**args):
    name = utils.find(args, "name")
    doc = frappe.get_doc("Agent", name)
    token = doc.get_password("access_token") or None

    client = Facebook(access_token=token)
    response = client.request(
        "GET",
        endpoint="/me",
        params={"fields": "email,name,picture"},
        headers={"authorization_type": "Bearer", "content_type": "json"}
    )
    
    profile = response.json()
    
    # audience_size = doc.get("audience_size")
    # if profile.get("public_metrics"):
    #     public_metrics = profile.get("public_metrics") or {}
    #     audience_size = public_metrics.get("followers_count") if public_metrics.get("followers_count") else None
    
    # Store page ID if available for future posting
    page_id = None
    if accounts:
        page_id = accounts[0].get("id")
    
    frappe.get_doc("Agent", name).update({
        "uid": profile.get("id"), 
        "display_name": profile.get("name"),
        "audience_size": audience_size,
        "page_id": page_id
    }).save()

    frappe.db.commit()

    return response


@frappe.whitelist()
def send(**args):
    name = utils.find(args, "name")
    agent = utils.find(args, "agent") or frappe.get_doc("Agent", name)
    text = utils.find(args, "text")
    image_path = utils.find(args, "image_path")
    activity_type = utils.find(args, "type")
    
    # Use page access token for posting, fallback to user token
    token = agent.get_password("page_access_token") or agent.get_password("access_token")
    if not token:
        frappe.throw(_("No access token found for Facebook agent"))
    
    client = Facebook(access_token=token)
    
    # Determine the posting endpoint based on token type
    endpoint = "/v18.0/me/feed"  # Default to user feed
    
    # Get page ID if using page token
    if agent.get_password("page_access_token"):
        # Get page ID from agent or use 'me' for simplicity
        page_id = agent.get("page_id") or "me"
        endpoint = f"/v18.0/{page_id}/feed"
    
    params = {"message": text}
    
    # Handle media upload if image provided
    if image_path:
        try:
            # Upload photo first
            photo_response = upload_photo(client, image_path, text, agent)
            if photo_response and photo_response.status_code == 200:
                return photo_response
        except Exception as e:
            frappe.log_error(f"Facebook media upload failed: {str(e)}")
    
    # Handle different activity types
    linked_external_id = utils.find(args, "linked_external_id")
    if linked_external_id and activity_type == "Post Comment":
        # Facebook doesn't support direct replies like Twitter
        # Instead, post as a comment on the original post
        endpoint = f"/v18.0/{linked_external_id}/comments"
        params = {"message": text}
    
    response = client.request(
        "POST",
        endpoint=endpoint,
        params=params,
        headers={"authorization_type": "Bearer"}
    )
    
    return response


def upload_photo(client, image_path, caption="", agent=None):
    """Upload photo to Facebook"""
    if image_path.startswith("http"):
        # Remote URL
        endpoint = "/v18.0/me/photos"
        if agent and agent.get_password("page_access_token"):
            page_id = agent.get("page_id") or "me"
            endpoint = f"/v18.0/{page_id}/photos"
            
        params = {
            "url": image_path,
            "caption": caption
        }
        return client.request(
            "POST",
            endpoint=endpoint,
            params=params,
            headers={"authorization_type": "Bearer"}
        )
    else:
        # Local file upload
        try:
            endpoint = f"{client.base_url}/v18.0/me/photos"
            if agent and agent.get_password("page_access_token"):
                page_id = agent.get("page_id") or "me"
                endpoint = f"{client.base_url}/v18.0/{page_id}/photos"
                
            with open(image_path, 'rb') as image_file:
                files = {'source': image_file}
                params = {'message': caption}
                
                response = requests.post(
                    endpoint,
                    files=files,
                    data=params,
                    headers={"Authorization": client.bearer()}
                )
                return response
        except Exception as e:
            frappe.log_error(f"Failed to upload Facebook photo: {str(e)}")
            return None