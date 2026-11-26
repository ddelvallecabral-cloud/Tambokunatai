from rest_framework.routers import SimpleRouter

from .views import AuditoriaViewSet

router = SimpleRouter(trailing_slash=False)
router.register("auditoria", AuditoriaViewSet, basename="auditoria")
urlpatterns = router.urls
