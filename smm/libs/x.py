import base64
import hashlib
import hmac
import json as JSON
import mimetypes
import os
import re
import sys
import time
from urllib.parse import quote, urlencode

import frappe
import requests
from frappe import _

from . import utils

MEDIA_ENDPOINT_URL = "https://upload.twitter.com/1.1/media/upload.json"


class X:
    def __init__(self, consumer_id=None, consumer_secret=None, client_id=None, client_secret=None, redirect_uri=None, access_token=None, access_token_secret=None,
refresh_token=None, scope=[], authorization_type=None, content_type=None, version=None):
        self.version = version or "oauth1" if consumer_id or consumer_secret else "oauth2" if client_id or client_secret else "oauth2"
        self.base_url = "https://api.twitter.com"
        self.request_token_url = "https://api.twitter.com/oauth/request_token"
        self.auth_url = "https://api.twitter.com/oauth/authorize" if self.version == "oauth1" else "https://twitter.com/i/oauth2/authorize" if self.version == "oauth2" else None
        self.consumer_id = consumer_id
        self.consumer_secret = consumer_secret
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope or ["tweet.read", "tweet.write", "tweet.moderate.write", "users.read", "follows.read", "follows.write", "offline.access", "space.read",
                               "mute.read", "mute.write", "like.read", "like.write", "list.read", "list.write", "block.read", "block.write", "bookmark.read", "bookmark.write"]
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.refresh_token = refresh_token
        self.authorization_type = authorization_type
        self.content_type = content_type
        self.state = None
        config = frappe.get_site_config() or {}
        domains = config.get("domains") or []
        protocol = "https" if config.get("ssl_certificate") else "http"

        # Check if frappe.local.request.host exists
        host = getattr(getattr(frappe.local, "request", {}), "host", "")
        self.redirect_uri = redirect_uri or ("https://skedew.com/redirect" if host == "localhost:8000" else f"{protocol}://{host or domains[0]}/api/method/smm.libs.x.callback")

    def bearer(self):
        return f"Bearer {self.access_token}"

    def basic(self):
        data = f"{self.client_id}:{self.client_secret}" if self.client_id and self.client_secret else f"{self.consumer_id}:{self.consumer_secret}" if self.consumer_id and self.consumer_secret else None
        return f"Basic {base64.b64encode(data.encode('utf-8')).decode('utf-8')}"

    def oauth(self, oauth_params={}):
        oauth_params = sorted(oauth_params.items())
        content = ', '.join([f'{key}="{self.percent_encode(str(value))}"' for key, value in oauth_params])
        return f"OAuth {content}"

    def authorization_header(self, type=None, oauth_params={}):
        type = type or self.authorization_type
        return self.bearer() if type == "Bearer" else self.basic() if type == "Basic" else self.oauth(oauth_params) if type == "OAuth" else None

    def content_type_header(self, type=None):
        type = type or self.content_type
        return "application/json" if type == "json" else "application/x-www-form-urlencoded" if type == "urlencoded" else "multipart/form-data" if type == "form" else None

    def headers(self, authorization_type=None, content_type=None, headers={}, method=None, url=None, params={}, data={}, json={}):
        authorization_type = authorization_type or headers.get("authorization_type") or self.authorization_type
        content_type = content_type or headers.get("content_type") or self.content_type
        oauth_params = {}
        headers = {}
        if self.version == "oauth1":
            oauth_params = self.sign_request(method=method, url=url, params={**params, **data, **json})
        if authorization_type:headers.update({"Authorization": self.authorization_header(authorization_type, oauth_params)})
        if content_type: headers.update({"Content-Type": self.content_type_header(content_type)})
        return headers
    
    def oauth_base_params(self, params={}):
        params = {
            "oauth_consumer_key": self.consumer_id,
            "oauth_nonce": self.verifier(),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_version": "1.0",
            **params
        }
        if self.access_token:
            params.update({"oauth_token": self.access_token})
        return params

    # Lexicographically sort parameters and urlencode them
    def encode_params(self, params):
        return urlencode(sorted(params.items()))

    # Percent encode
    def percent_encode(self, string):
        return re.sub(r"([^a-zA-Z0-9-_\.~])", lambda m: f"%{ord(m.group(1)):02X}", string)

    def signature(self, key, string):
        return base64.b64encode(hmac.new(key.encode("utf-8"), string.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
        
    def sign_request(self, method=None, url=None, params={}):
        oauth_params = self.oauth_base_params(params)
        for key, value in oauth_params.items():
            if key.startswith("oauth_"):
                oauth_params[key] = self.percent_encode(value)
        base_url = url.split("?")[0]
        base_url = self.percent_encode(base_url)
        base_string = f"{method.upper()}&{base_url}&{self.percent_encode(self.encode_params(oauth_params))}"
        signing_key = f"{self.percent_encode(self.consumer_secret)}&"
        if self.access_token_secret:
            signing_key += f"{self.percent_encode(self.access_token_secret)}"
        signature = self.signature(signing_key, base_string)
        oauth_params.update({"oauth_signature": signature})
        return oauth_params
    
    # Generate random string
    def verifier(self):
        return re.sub("[^a-zA-Z0-9]+", "", base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8"))

    def challenge(self, verifier):
        return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest()).decode("utf-8").replace("=", "")

    # Generate new state with unique random string
    # This state will be used to verify the requests/responses
    def new_state(self):
        self.state = self.verifier()
        return self.state

    def request(self, method="GET", url=None, endpoint=None, params={}, data={}, json={}, headers={}, request=True, files={},**args):
        url = url or self.base_url + endpoint

        headers = self.headers(headers=headers, method=method, url=url, params=params, data=data, json=json)
        # if utils.find(args, "files"):
        #     del headers["Content-Type"] # If files present, let requests library handle content type
        if headers.get("Content-Type") == "application/json":
            data = JSON.dumps(data)
            json = JSON.dumps(json)
        # Complete URL with encoded parameters
        if method == "GET" and not request:
            return url + "?" + urlencode(params)
        if request:
            return requests.request(method, url, params=params, data=data, json=json, headers=headers, files=files)

    # Returns authorization URL, state, code_verifier, code_challenge, code_challenge_method
    def authorize(self, redirect_uri=None, scope=[], state=None, code_verifier=None, code_challenge=None, code_challenge_method="S256"):
        scope = scope or self.scope
        state = state or self.new_state()
        code_verifier = code_verifier or self.verifier()
        code_challenge = code_challenge or self.challenge(code_verifier)
        code_challenge_method = code_challenge_method or "S256"
        if self.version == "oauth1":
            request_token = self.request_token()
            if request_token.status_code == 200:
                # On success request, the raw response content is a string "oauth_token=Z6eEdO8MOmk394WozF5oKyuAv855l4Mlqo7hhlSLik&oauth_token_secret=Kd75W4OQfb2oJTV0vzGzeXftVAwgMnEK9MumzYcM&oauth_callback_confirmed=true"
                # Parse the response content to get oauth_token and oauth_token_secret
                response = dict([pair.split("=") for pair in request_token.content.decode("utf-8").split("&")])
                oauth_token = response.get("oauth_token")
                state = oauth_token # OAuth 1 doesn't have state, so we use oauth_token instead
                oauth_token_secret = response.get("oauth_token_secret") # Don't know what to do with this but it's referenced in the docs
                self.access_token_secret = response.get("oauth_token_secret")
                oauth_callback_confirmed = response.get("oauth_callback_confirmed")
                if oauth_callback_confirmed:
                    url = self.request("GET", url=self.auth_url, params={"oauth_token": oauth_token}, request=False)

        if self.version == "oauth2":
            params = {
                "state": state,
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": redirect_uri or self.redirect_uri,
                "scope": " ".join(scope),
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method
            }
            url = self.request("GET", url=self.auth_url, params=params, request=False)

        return url, state, code_verifier, code_challenge, code_challenge_method

    # For OAuth 1: Exchange oauth_consumer_key for oauth_token
    def request_token(self, consumer_id=None, redirect_uri=None):
        consumer_id = consumer_id or self.consumer_id
        redirect_uri = redirect_uri or self.redirect_uri
        
        if not consumer_id:
            return
        return self.request(
            "POST",
            url=self.request_token_url,
            data={
                "oauth_consumer_key": consumer_id
            },
            headers={
                "authorization_type": "OAuth"
            }
        )

    # Get access token from code
    def token(self, oauth_token=None, oauth_verifier=None, code_verifier=None, code=None, redirect_uri=None):
        if self.version == "oauth1":
            if not oauth_token or not oauth_verifier:
                return
            return self.request(
                "POST",
                endpoint="/oauth/access_token",
                params={
                    "oauth_consumer_key": self.consumer_id,
                    "oauth_token": oauth_token,
                    "oauth_verifier": oauth_verifier
                },
                headers={
                    "authorization_type": "Basic",
                    "content_type": "urlencoded"
                }
            )
        
        if self.version == "oauth2":
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
            headers={
                "authorization_type": "Basic",
                "content_type": "urlencoded"
            }
        )
    
    # Upload media file
    def upload(self, file):
        self._upload_init(file=file)
        self._upload_append()
        self._upload_finalize()

        return {"media_id": self.media_id, "status": "ok"}

    def _get_media_category(self):
        """
        Determines media category based on MIME type
        """
        mime_type, _ = mimetypes.guess_type(self.file)
        if mime_type:
            if mime_type.startswith("image"):
                return "tweet_image"
            elif mime_type.startswith("video"):
                return "tweet_video"
            elif mime_type.startswith("audio"):
                return "tweet_audio"  # You can define this category if needed

        return None  # Unable to determine MIME type

    def _upload_init(self, file):
        """
        Initializes Upload
        """
        print("INIT")
        self.file = file
        self.total_bytes = os.path.getsize(self.file)
        self.media_id = None
        self.processing_info = None
        mime_type, _ = mimetypes.guess_type(self.file)
        params = {
            "command": "INIT",
            "media_type": mime_type,
            "total_bytes": self.total_bytes,
        }
        media_category = self._get_media_category()
        if media_category:
            params["media_category"] = media_category

        req = self.request(
            method="POST",
            url=MEDIA_ENDPOINT_URL,
            params=params,
            headers={
                "authorization_type": "OAuth",
            },
        )
        print(req.json())
        media_id = req.json()["media_id"]

        self.media_id = media_id

        print("Media ID: %s" % str(media_id))

    def _upload_append(self):
        """
        Uploads media in chunks and appends to chunks uploaded
        """
        segment_id = 0
        bytes_sent = 0
        file = open(self.file, "rb")

        while bytes_sent < self.total_bytes:
            chunk = file.read(4 * 1024 * 1024)

            print("APPEND")

            params = {
                "command": "APPEND",
                "media_id": self.media_id,
                "segment_index": segment_id,
            }

            files = {"media": chunk}

            req = self.request(
                method="POST",
                url=MEDIA_ENDPOINT_URL,
                params=params,
                files=files,
                headers={
                    "authorization_type": "OAuth",
                },
            )
            if req.status_code < 200 or req.status_code > 299:
                print(req.status_code)
                print(req.text)
                sys.exit(0)

            segment_id = segment_id + 1
            bytes_sent = file.tell()

            print("%s of %s bytes uploaded" %
                  (str(bytes_sent), str(self.total_bytes)))

        print("Upload chunks complete.")

    def _upload_finalize(self):
        """
        Finalizes uploads and starts video processing
        """
        print("FINALIZE")

        params = {"command": "FINALIZE", "media_id": self.media_id}

        req = self.request(
            method="POST",
            url=MEDIA_ENDPOINT_URL,
            params=params,
            headers={"authorization_type": "OAuth"},
        )

        self.processing_info = req.json().get("processing_info", None)
        self._upload_check_status()

    def _upload_check_status(self):
        """
        Checks video processing status
        """
        if self.processing_info is None:
            return

        state = self.processing_info["state"]

        print("Media processing status is %s " % state)

        if state == "succeeded":
            return

        if state == "failed":
            sys.exit(0)

        check_after_secs = self.processing_info["check_after_secs"]

        print("Checking after %s seconds" % str(check_after_secs))
        time.sleep(check_after_secs)

        print("STATUS")

        params = {"command": "STATUS", "media_id": self.media_id}

        req = self.request(
            method="POST",
            url=MEDIA_ENDPOINT_URL,
            params=params,
            headers={"authorization_type": "OAuth"},
        )
        self.processing_info = req.json().get("processing_info", None)
        self.check_status()


@frappe.whitelist()
def authorize(**args):
    version = utils.find(args, "version") or "oauth2" # Must be "oauth1" or "oauth2"
    unsaved = utils.find(args, "__unsaved")
    name = utils.find(args, "name") if not unsaved else None
    api = utils.find(args, "api")
    if not api:
        frappe.msgprint(_("{0} is empty").format(_("API")))
        return
    doc = frappe.get_doc("API", api)
    consumer_id = doc.get_password("consumer_id") or None
    consumer_secret = doc.get_password("consumer_secret") or None
    client_id = doc.get_password("client_id") or None
    client_secret = doc.get_password("client_secret") or None
    credentials = {}
    if version == "oauth1":
        if not consumer_id or not consumer_secret:
            frappe.msgprint(_("Consumer ID or Consumer Secret or both not found"))
            return
        credentials.update({"consumer_id": consumer_id, "consumer_secret": consumer_secret})
    if version == "oauth2":
        if not client_id or not client_secret:
            frappe.msgprint(_("Client ID or Client Secret or both not found"))
            return
        credentials.update({"client_id": client_id, "client_secret": client_secret})

    client = X(**credentials)

    url, state, code_verifier, code_challenge, code_challenge_method = client.authorize()

    session_data = {
        "state": state,
        "user": frappe.session.user,
        "API": api,
        "version": version,
        "consumer_id": consumer_id,
        "consumer_secret": consumer_secret,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": code_verifier,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }

    if name:
        session_data["name"] = name

    # Save session data to frappe cache so that it can be used later for verification
    frappe.cache().set_value(state, JSON.dumps(session_data))

    return {"state": state, "authorization_url": url}


@frappe.whitelist()
def callback(**args):
    error = args.get("error")
    oauth_token, oauth_verifier = args.get("oauth_token"), args.get("oauth_verifier")
    state = args.get("state") or oauth_token or None
    code = args.get("code") or None
    
    if error:
        redirect_url = "/app/agent"
        frappe.local.response.update({"type": "redirect", "location": redirect_url, "message": _("Redirecting to {0}").format(_("Agent"))})
        return
    
    if not state:
        return
    
    # Try to get session data from frappe cache using state
    data = frappe.cache().get_value(state)
    
    # Delete frappe cache to release memory
    frappe.cache().delete_value(state)
    
    if data:
        session = JSON.loads(data)
        version = session.get("version")
        name = session.get("name")
        api = session.get("API")
        api = frappe.get_doc("API", api)
        
        tokens = None
        
        if version == "oauth1" and oauth_token and oauth_verifier:
            consumer_id = session.get("consumer_id") or api.get_password("consumer_id") or None
            consumer_secret = session.get("consumer_secret") or api.get_password("consumer_secret") or None
            client = X(consumer_id=consumer_id, consumer_secret=consumer_secret)
            
            response = client.token(oauth_token=oauth_token, oauth_verifier=oauth_verifier)
            
            if response.status_code == 200:
                response = dict([pair.split("=") for pair in response.content.decode("utf-8").split("&")])
                if "oauth_token" not in response:
                    frappe.throw("Access token not received. Authorization failed.")

                tokens = {
                    "oauth1_access_token": response.get("oauth_token"),
                    "oauth1_token_secret": response.get("oauth_token_secret"),
                }

        if version == "oauth2" and state and code:
            client_id = session.get("client_id") or api.get_password("client_id") or None
            client_secret = session.get("client_secret") or api.get_password("client_secret") or None
            code_verifier = session.get("code_verifier")
            client = X(client_id=client_id, client_secret=client_secret)

            response = client.token(code_verifier=code_verifier, code=code)
            
            if response.status_code == 200:
                response = response.json()
                if "access_token" not in response:
                    frappe.throw("Access token not received. Authorization failed.")

                tokens = {
                    "access_token": response.get("access_token"),
                    "refresh_token": response.get("refresh_token")
                }
        
        if tokens:
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

    client = X(client_id=client_id, client_secret=client_secret)

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

    client = X(access_token=token)
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
    activity_type = utils.find(args, "type")
    text = utils.find(args, "text")
    image_path = utils.find(args, "image_path")
    token = agent.get_password("access_token") or None
    api = utils.find(args, "api") or frappe.get_doc("API", "c7618067fe")
    client = X(access_token=token)

    # below credentials using for upload media
    oauth1_access_token = agent.get_password("oauth1_access_token") or None
    oauth1_token_secret = agent.get_password("oauth1_token_secret") or None
    consumer_id = api.get_password("consumer_id") or None
    consumer_secret = api.get_password("consumer_secret") or None

    linked_external_id = utils.find(args, "linked_external_id")

    params = {"text": text}
    if linked_external_id:
        types = {
            "Post Comment": {"reply": {"in_reply_to_tweet_id": linked_external_id}},
            "Share Content": {"quote_tweet_id": linked_external_id},
        }
        param = types.get(activity_type)
        params.update(param)

    # Upload media if possible
    if image_path:
        client_oauth1 = X(
            consumer_id=consumer_id,
            consumer_secret=consumer_secret,
            access_token=oauth1_access_token,
            access_token_secret=oauth1_token_secret,
        )
        upload_res = client_oauth1.upload(file=image_path)
        print("TEST", upload_res)
        params["media"] = [upload_res["media_id"]]
    # Send final content
    response = client.request(
        "POST",
        endpoint="/2/tweets",
        json=params,
        headers={"authorization_type": "Bearer", "content_type": "json"},
    )

    return response

# IMPORTANT: This function is under development and not working yet, because API needs to be upgraded to Basic tier, which is paid.
# This function requires a paid API subscription
@frappe.whitelist()
def fetch(**args):
    # bench --site erp.mimiza.com execute smm.libs.x.fetch --kwargs '{"keyword":"bitcoin","api":"2578e8f666"}'
    name = utils.find(args, "name")
    keyword = utils.find(args, "keyword")
    # agent = frappe.get_doc("Agent", name or utils.find(args, "agent"))
    api = utils.find(args, "api")
    api = frappe.get_doc("API", api)
    token = api.get_password("token") or None
    client = X(access_token=token)
    client.request(
        "GET",
        endpoint="/2/tweets/search/recent",
        params={"query": keyword},
        headers={"authorization_type": "Bearer", "content_type": "json"}
    )
    return True