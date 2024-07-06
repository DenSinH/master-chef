import typing as t
from jinja2 import FileSystemLoader
from htmlmin import Minifier


class MinifyingFileSystemLoader(FileSystemLoader):
    """
    A template loader that minifies HTML templates
    on load, reducing processing time for rendering
    """

    minifier = Minifier(
        remove_empty_space=True
    )

    def get_source(
        self, environment: "Environment", template: str
    ) -> t.Tuple[str, str, t.Callable[[], bool]]:
        contents, path, uptodate = super().get_source(environment, template)
        return self.minifier.minify(contents), path, uptodate
