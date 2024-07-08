from typing import Callable, TYPE_CHECKING
from jinja2 import FileSystemLoader
from htmlmin import Minifier

if TYPE_CHECKING:
    from jinja2.environment import Environment


class MinifyingFileSystemLoader(FileSystemLoader):
    """
    A template loader that minifies HTML templates
    on load, reducing processing time for rendering
    """

    minifier = Minifier(
        remove_empty_space=True
    )

    def get_source(
        self, environment: 'Environment', template: str
    ) -> tuple[str, str, Callable[[], bool]]:
        """ Load and minify source """
        contents, path, uptodate = super().get_source(environment, template)
        return self.minifier.minify(contents), path, uptodate
