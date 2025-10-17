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
        self.query_email_html = self.directory + "query_email.html"
        self.invoice_created = self.directory + "invoice_created.html"
        self.transaction_created = self.directory + "transaction_created.html"
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

    def QueryEmail(
        self,
        firstName,
        lastName,
        email,
        phone,
        companyName,
        industry,
        companySize,
        message,
        queryId,
        queryType,
        time,
    ):
        """QUERY_EMAIL
        --------------------
        Generates a query email template with the provided details.
        Parameters:
        - name: Name of the user.
        - role: Role of the user (e.g., admin, user).
        - email: Email address of the user.
        - password: Password for the user.
        Returns:
        - Rendered HTML string for the query email.
        """

        parser = {
            "firstName": firstName,
            "lastName": lastName,
            "email": email,
            "phone": phone,
            "companyName": companyName,
            "industry": industry,
            "companySize": companySize,
            "message": message,
            "queryId": queryId,
            "queryType": queryType,
            "timestamp": time,
        }
        return self.render_template(self.query_email_html, parser)

    def InvoiceCreated(
        self,
        invoice_number,
        invoice_date,
        customer_name,
        total_amount,
        due_date,
        payment_status,
        # invoice_link,
    ):
        """INVOICE_CREATED
        --------------------
        Generates an invoice created email template with the provided details.
        Parameters:
        - invoice_number: Invoice number.
        - invoice_date: Invoice date.
        - customer_name: Name of the customer.
        - total_amount: Total amount of the invoice.
        - due_date: Due date of the invoice.
        - payment_status: Payment status of the invoice.
        Returns:
        - Rendered HTML string for the invoice created email.
        """

        parser = {
            "domain": self.domain,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "customer_name": customer_name,
            "total_amount": total_amount,
            "due_date": due_date,
            "payment_status": payment_status,
            # "invoice_link": invoice_link,
            "domain_login": self.domain_login,
        }
        return self.render_template(self.invoice_created, parser)

    def TransactionCreated(
        self,
        user_name,
        transaction_type,
        customer_name,
        currency_symbol,
        reference_note,
        transaction_date,
        amount,
        support_link,
    ):
        """TRANSACTION_CREATED
        --------------------
        Generates a transaction created email template with the provided details.
        Parameters:
        - user_name: Name of the user.
        - transaction_type: Type of the transaction.
        - customer_name: Name of the customer.
        - currency_symbol: Currency symbol.
        - reference_note: Reference note for the transaction.
        - transaction_date: Date of the transaction.
        - amount: Amount of the transaction.
        - support_link: Support link.
        Returns:
        - Rendered HTML string for the transaction created email.
        """

        parser = {
            "domain": self.domain,
            "customer_name": customer_name,
            "user_name": user_name,
            "transaction_type": transaction_type,
            "currency_symbol": currency_symbol,
            "reference_note": reference_note,
            "transaction_date": transaction_date,
            "amount": amount,
            "support_link": support_link,
            "domain_login": self.domain_login,
        }
        return self.render_template(self.transaction_created, parser)



"""------------------------------------------------------------------------------------------------------------------------
                                                    TEMPLATE MODULE
------------------------------------------------------------------------------------------------------------------------"""
