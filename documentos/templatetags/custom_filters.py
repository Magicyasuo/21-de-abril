from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(value, css_class):
        try:
            return value.as_widget(attrs={"class": css_class})
        except AttributeError:
            # Si el valor no tiene el método `as_widget`, lo devolvemos sin cambios
            return value
