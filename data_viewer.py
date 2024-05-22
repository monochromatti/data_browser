from pathlib import Path

import hvplot.polars
import panel as pn
import param
import polars as pl

pn.extension("plotly")


class FileExplorer(param.Parameterized):
    rootdir = param.String(default="/")
    directories = param.ListSelector(objects=[])
    files = param.ListSelector(objects=[])
    selected_files = param.ListSelector(objects=[])
    comment_prefix = param.ObjectSelector(
        default="#",
        objects=["#", "%", "//", ";"],
    )
    separator_char = param.ObjectSelector(
        default="\t",
        objects=["\t", ",", ";", " "],
    )
    separator_labels = param.List(
        default=[r"\t", ",", ";", " "],
        constant=True,
    )
    has_header = param.Boolean(default=False)
    column_ids = param.List(default=[1, 2])

    data = param.ClassSelector(class_=pl.DataFrame, default=pl.DataFrame())

    def __init__(self, **params):
        super().__init__(**params)
        self.rootdir_widget = pn.widgets.TextInput(
            name="Root directory",
            value=self.rootdir,
            sizing_mode="stretch_width",
            margin=25,
        )

        self.selected_folders = []
        self.dir_selector = pn.widgets.MultiSelect(
            name="Directories",
            options=[],  # Initialize with an empty list
            size=20,
            sizing_mode="stretch_width",
            margin=25,
        )
        self.file_selector = pn.widgets.MultiSelect(
            name="Files",
            options=[],  # Initialize with an empty list
            size=40,
            sizing_mode="stretch_both",
            margin=25,
        )
        self.comment_prefix_widget = pn.widgets.Select(
            name="Comment prefix",
            options=self.param.comment_prefix.objects,
            sizing_mode="stretch_width",
        )
        self.separator_char_widget = pn.widgets.Select(
            name="Separator character",
            options=self.param.separator_labels,
            sizing_mode="stretch_width",
        )
        self.has_header_widget = pn.widgets.Checkbox(
            name="Header",
            value=self.param.has_header,
            align="center",
        )
        self.column_ids_widget = pn.widgets.TextInput(
            name="Columns",
            value="1,2",
            sizing_mode="stretch_width",
        )
        self.csv_params_widget = pn.Row(
            self.comment_prefix_widget,
            self.separator_char_widget,
            self.column_ids_widget,
            self.has_header_widget,
            sizing_mode="stretch_width",
            margin=25,
        )

        self.file_column = pn.Column(
            "# Browse",
            self.rootdir_widget,
            self.dir_selector,
            self.file_selector,
            self.csv_params_widget,
            styles=dict(background="WhiteSmoke"),
            width=720,
            height=1280,
        )

        self._setup_bindings()
        self._update_directories()
        self._update_files()

    @param.depends("rootdir", watch=True)
    def _update_directories(self, event=None):
        self.directories = self.get_directories(self.rootdir)
        self.dir_selector.options = self.directories

    @param.depends("directories", watch=True)
    def _update_files(self, event=None):
        self.files = self.get_files(self.selected_folders)
        self.file_selector.options = self.files

    def get_directories(self, rootdir):
        try:
            return sorted([d.name for d in Path(rootdir).iterdir() if d.is_dir()])
        except FileNotFoundError:
            return []

    def get_files(self, folders):
        try:
            files = []
            for folder in folders:
                for f in Path(self.rootdir, folder).iterdir():
                    if f.is_file():
                        files.append(str(f.relative_to(self.rootdir)))
            return files
        except FileNotFoundError:
            return []

    @param.depends("selected_files", watch=True)
    def _load_files_to_df(self, event=None):
        if not self.selected_files:
            self.param.update(data=pl.DataFrame())
        else:
            dfs = []
            for file in self.selected_files:
                df = (
                    pl.read_csv(
                        Path(self.rootdir, file),
                        separator=self.separator_char,
                        has_header=self.has_header,
                        comment_prefix=self.comment_prefix,
                    )
                    .select(f"column_{i}" for i in self.column_ids)
                    .with_columns(pl.lit(file).alias("filename"))
                )
                dfs.append(df)
            self.param.update(data=pl.concat(dfs) if dfs else pl.DataFrame())

    def _sync_rootdir(self, event):
        self.rootdir = event.new

    def _update_selected_folders(self, event):
        self.selected_folders = self.dir_selector.value
        self._update_files()

    def _update_selected_files(self, event):
        self.selected_files = self.file_selector.value

    def _update_separator_char(self, event):
        self.separator_char = event.new

    def _update_comment_prefix(self, event):
        self.comment_prefix = event.new

    def _update_has_header(self, event):
        self.has_header = event.new

    def _update_column_ids(self, event):
        self.column_ids = [int(col.strip()) for col in event.new.split(",")]

    def _setup_bindings(self):
        bindings = [
            (self.rootdir_widget, self._sync_rootdir, "value"),
            (self.dir_selector, self._update_files, "value"),
            (self.dir_selector, self._update_selected_folders, "value"),
            (self.file_selector, self._update_selected_files, "value"),
            (self.comment_prefix_widget, self._update_comment_prefix, "value"),
            (self.separator_char_widget, self._update_separator_char, "value"),
            (self.has_header_widget, self._update_has_header, "value"),
            (self.column_ids_widget, self._update_column_ids, "value"),
        ]

        for widget, method, parameter in bindings:
            widget.param.watch(method, parameter)


class FileViewer(param.Parameterized):
    selected_file = param.String(default="")
    column_ids = param.List(default=[1, 2])

    def __init__(self, file_explorer, **params):
        super().__init__(**params)
        self.file_explorer = file_explorer

        self.data_selector = pn.widgets.Select(
            name="File",
            options=[],
            size=10,
            sizing_mode="stretch_width",
        )
        self.header_text = pn.pane.Markdown(object="", sizing_mode="stretch_both")

        self.frame_view = pn.pane.DataFrame(
            sizing_mode="stretch_both", index=False, header=True
        )

        self.settings_column = pn.Column(
            self.data_selector,
            self.header_text,
        )
        self.frame_row = pn.Row(self.settings_column, self.frame_view)
        self.inspect_pane = pn.Column(
            "# Inspect",
            self.frame_row,
            styles=dict(background="WhiteSmoke"),
        )

        self._setup_bindings()
        self._update_files()

    def load_frame(self, file, col_ids, **kwargs):
        df = pl.read_csv(file, **kwargs)
        if not kwargs.get("has_header", True):
            col_ids = [f"column_{i}" for i in col_ids]
        return df.select(col_ids)

    def load_header(self, file, comment_prefix):
        lines = []
        with open(file) as f:
            for line in f:
                if line.startswith(comment_prefix):
                    lines.append(line.strip(comment_prefix).strip())
                else:
                    break
        return "\n".join(lines)

    @param.depends("selected_file", "column_ids", watch=True)
    def update_frame(self, event=None):
        selected_file = self.data_selector.value
        if selected_file:
            file_path = Path(self.file_explorer.rootdir, selected_file)
            try:
                frame = (
                    self.file_explorer.data.filter(pl.col("filename") == selected_file)
                    .select(pl.all().exclude("filename"))
                    .to_pandas()
                )
                self.frame_view.object = frame
                header = self.load_header(file_path, self.file_explorer.comment_prefix)
                self.header_text.object = "**Header**\n\n" + header
            except Exception as e:
                self.frame_view.object = pn.pane.Markdown(
                    f"Error loading file: {e}", sizing_mode="stretch_both"
                )
                self.header_text.object = ""
        else:
            self.frame_view.object = pn.pane.Markdown(
                "No file selected", sizing_mode="stretch_both"
            )
            self.header_text.object = ""

    def _setup_bindings(self):
        self.file_explorer.param.watch(self._update_files, "selected_files")
        self.data_selector.param.watch(self.update_frame, "value")

    def _update_files(self, event=None):
        if self.file_explorer.selected_files:
            self.data_selector.options = self.file_explorer.selected_files
        else:
            self.data_selector.options = []
        self.update_frame()


class DataPlotter(param.Parameterized):
    file_explorer = param.Parameter()

    def __init__(self, file_explorer, **params):
        super().__init__(file_explorer=file_explorer, **params)
        self.plot = self.create_empty_plot()
        self.plot_pane = pn.pane.HoloViews(
            self.plot,
            sizing_mode="stretch_both",
            margin=25
        )
        self.plot_column = pn.Column(
            "# View",
            self.plot_pane,
            styles=dict(background="WhiteSmoke"),
        )

        self._setup_bindings()
        self.update_plot()

    @param.depends("file_explorer.data", watch=True)
    def update_plot(self, event=None):
        data = self.file_explorer.data
        if not data.is_empty():
            new_plot = data.hvplot.line(
                x="column_1", y="column_2", by="filename", legend=False
            )
        else:
            new_plot = self.create_empty_plot()

        self.plot_pane.object = new_plot

    def create_empty_plot(self):
        # Create an empty plot or a placeholder message
        return pl.DataFrame({"x": [], "y": [], "filename": []}).hvplot.line(
            x="x", y="y"
        )

    def _setup_bindings(self):
        self.file_explorer.param.watch(self.update_plot, "data")


file_explorer = FileExplorer()
file_viewer = FileViewer(file_explorer)
data_plotter = DataPlotter(file_explorer)

app = pn.Row(
    file_explorer.file_column,
    pn.Column(
        file_viewer.inspect_pane,
        data_plotter.plot_column,
    ),
)
app.servable()
