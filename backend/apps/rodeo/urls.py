from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("animales", views.AnimalViewSet, basename="animal")

urlpatterns = [path("rodeo/ordene", views.ordene, name="rodeo-ordene"), *router.urls]
