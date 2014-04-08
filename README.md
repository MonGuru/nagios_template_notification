 Nagios Template Notification plugin
=====================


This is a Nagios notification plugin that allows you using python's [Jinja2 template language](http://jinja.pocoo.org/docs/).
It comes with working html template that can be sent via email. The example template is based on the ["Send HTML Alert Email v2"](http://exchange.nagios.org/directory/Addons/Notifications/Send-HTML-Alert-Email-v2/details).

----------

You can create your own class/template to render and send the notification message.
It contains a class named SchemaWebService which you can use as an example to build your own.
