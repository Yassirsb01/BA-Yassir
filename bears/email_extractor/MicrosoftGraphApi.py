import msal
import dotenv
import os

dotenv.load_dotenv()

# Token-Cache wird lokal gespeichert -> einmaliger Login reicht
TOKEN_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_cache.json")


class MicrosoftGraphApi:
    """
    Microsoft Graph API Client fuer Delegate Permissions (Device Code Flow).

    Delegate Permissions bedeuten: die App handelt im Namen eines Benutzers.
    Beim ersten Start muss sich der Benutzer einmalig im Browser authentifizieren.
    Danach wird der Token automatisch erneuert (Refresh Token, 90 Tage gueltig).

    Token wird lokal in token_cache.json gespeichert.
    """

    def __init__(self):
        self.tenant_id = os.getenv("TENANT_ID")
        self.client_id = os.getenv("CLIENT_ID")
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        # Delegate Scopes (Mail lesen + schreiben + als gelesen markieren)
        self.scope = ["https://graph.microsoft.com/Mail.ReadWrite"]

        # Token-Cache laden (aus vorherigem Login)
        self.cache = msal.SerializableTokenCache()
        if os.path.exists(TOKEN_CACHE_FILE):
            try:
                with open(TOKEN_CACHE_FILE, "r") as f:
                    self.cache.deserialize(f.read())
                print(f"✅ Token-Cache geladen aus {TOKEN_CACHE_FILE}")
            except Exception as e:
                print(f"⚠️ Token-Cache konnte nicht geladen werden: {e}")

        # PublicClientApplication fuer Delegate Flow (kein client_secret noetig)
        self.app = msal.PublicClientApplication(
            self.client_id,
            authority=self.authority,
            token_cache=self.cache,
        )

    def _save_cache(self):
        """Speichert Token-Cache nach jeder Aktualisierung."""
        if self.cache.has_state_changed:
            try:
                with open(TOKEN_CACHE_FILE, "w") as f:
                    f.write(self.cache.serialize())
            except Exception as e:
                print(f"⚠️ Token-Cache konnte nicht gespeichert werden: {e}")

    def get_access_token(self) -> str | None:
        """
        Token holen - zuerst aus Cache (silent), dann Device Code Flow.

        Beim ersten Aufruf: Browser-Login erforderlich (einmalig).
        Danach: automatische stille Erneuerung via Refresh Token.
        """
        # Versuch 1: Token aus Cache (silent refresh)
        accounts = self.app.get_accounts()
        result = None

        if accounts:
            result = self.app.acquire_token_silent(self.scope, account=accounts[0])

        if result and "access_token" in result:
            self._save_cache()
            return result["access_token"]

        # Versuch 2: Device Code Flow (einmaliger Browser-Login)
        print("\n" + "=" * 60)
        print("EINMALIGE AUTHENTIFIZIERUNG ERFORDERLICH")
        print("Bitte einmalig im Browser einloggen:")
        print("=" * 60)

        flow = self.app.initiate_device_flow(scopes=self.scope)

        if "user_code" not in flow:
            raise Exception(
                f"Device Code Flow fehlgeschlagen: {flow.get('error_description', 'Unbekannter Fehler')}"
            )

        # Zeigt z.B.: "Öffne https://microsoft.com/devicelogin und gib den Code ABCD-1234 ein"
        print(flow["message"])
        print("=" * 60 + "\n")

        # Wartet bis der Benutzer sich im Browser eingeloggt hat
        result = self.app.acquire_token_by_device_flow(flow)

        if "access_token" not in result:
            raise Exception(
                f"Authentifizierung fehlgeschlagen: {result.get('error_description', 'Unbekannter Fehler')}"
            )

        self._save_cache()
        print("✅ Authentifizierung erfolgreich! Token gespeichert in token_cache.json")
        print("ℹ️  Ab jetzt läuft die App automatisch ohne erneuten Login.\n")

        return result["access_token"]


if __name__ == "__main__":
    api = MicrosoftGraphApi()
    token = api.get_access_token()
    print(f"Token: {token[:30]}..." if token else "Kein Token erhalten")