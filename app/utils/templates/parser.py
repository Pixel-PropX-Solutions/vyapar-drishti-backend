"""------------------------------------------------------------------------------------------------------------------------
                                                    TEMPLATE MODULE
------------------------------------------------------------------------------------------------------------------------
"""

from datetime import datetime
from app.Config import ENV_PROJECT


class Template:
    """
    TEMPLATE MODULE
    ---------------
    Parser for Dynamic html Render & Storage

    ATTRIBUTES
    ----------
    - directory
    - challenge_html
    - confirmation_html
    - admin_html
    - credentials_html
    - welcome_html
    - recovery_html

    METHODS
    -------
    - render_template( path, parser )
    - Challenge( link, agenda )
    - Credentials( Merchant_ID, Merchant_PIN, API_KEY, agenda )
    - Recovery( today )
    ...
    """

    # --------------------------------------------------------------------------------------------------------------------------

    def __init__(self, domain, env):
        # Initialise html paths
        self.directory = "app/utils/templates/mail/"
        self.domain = domain
        self.domain_login = domain + "/login"
        self.onboard_html = self.directory + "onboard.html"
        self.password_request_html = self.directory + "password_request.html"
        self.forgot_password = self.directory + "forgot_password.html"
        self.subdomain = "dev" if env == "dev" else ""

    # --------------------------------------------------------------------------------------------------------------------------

    def render_template(self, path, parser):
        """
        RENDER_TEMPLATE
        ---------------
        Renders the html file from *path* by replacing *parser* arguments,
        and returns the rendered string.
        ...
        """

        # Open html file
        with open(
            path,
            "r",
            encoding="utf8",
        ) as html:
            # Extract content
            content = html.read()
            # Replace parser arguments
            for key in parser:
                content = content.replace(
                    "{" + key + "}",
                    str(parser[key]),
                )
            # content = content.replace(
            #     "{domain}",
            #     self.domain,
            # )
            # Return content
            return content

    # --------------------------------------------------------------------------------------------------------------------------

    def ForgotPassword(self, link, agenda=""):
        """
        FORGOT_PASSWORD_TEMPLATE
        --------------------
        ...
        """

        # parser arguments

        parser = {"link": link, "domain": self.domain, "domain_login": self.domain_login}

        # return merchant password reset alert html
        if agenda == "forgot_password":
            return self.render_template(
                self.forgot_password,
                parser,
            )

    # --------------------------------------------------------------------------------------------------------------------------

    def Onboard(self, verification_link, name):
        parser = {
            "verify_link": verification_link,
            "name": name,
            "domain": self.domain,
            "domain_login": self.domain_login,
        }
        return self.render_template(self.onboard_html, parser)

    def PasswordRequest(self, name, role, email, password):
        """PASSWORD_REQUEST
        --------------------
        Generates a password request email template with the provided details.
        Parameters:
        - name: Name of the user.
        - role: Role of the user (e.g., admin, user).
        - email: Email address of the user.
        - password: Password for the user.
        Returns:
        - Rendered HTML string for the password request email.
        """

        parser = {
            "link": "https://" + self.subdomain + role + self.domain,
            "name": name,
            "email": email,
            "password": password,
            "role": role,
        }
        return self.render_template(self.password_request_html, parser)


"""------------------------------------------------------------------------------------------------------------------------
                                                    TEMPLATE MODULE
------------------------------------------------------------------------------------------------------------------------"""
