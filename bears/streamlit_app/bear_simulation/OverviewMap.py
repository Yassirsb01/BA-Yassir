import dash
from dash import html
import folium
from datetime import datetime
from MedianCalculator import MedianCalculator
from ClusterCalculator import ClusterCalculator
from GeoToolBox import GeoToolBox
from pyproj import Transformer
from collections import Counter


class OverviewMap:
    def __init__(self, title, points, with_clusters=False, medians=None, outliers=None):
        self.points = points
        self.title = title
        self.medians = medians
        self.outliers = outliers
        self.with_clusters = with_clusters

    def show(self):

        points = []
        for point in self.points:
            if self.with_clusters:
                lat, lon, _ = point
            else:
                lat, lon = point
            points.append((lat, lon))

        center_lat = sum(lat for lat, _ in points) / len(points)
        center_lon = sum(lon for _, lon in points) / len(points)
        sightings_map = folium.Map(location=[center_lat, center_lon], zoom_start=7)

        colors = {
            0: "red",
            1: "blue",
            2: "purple",
            3: "orange",
            4: "yellow",
            5: "pink"
        }

        for point in self.points:
            if self.with_clusters:
                lat, lon, nr = point
                if nr in colors:
                    color = colors[nr]
                else:
                    color = "brown"
            else:
                lat, lon = point
                color = colors[0]

            folium.CircleMarker(
                location=[lat, lon],
                popup=folium.Popup("Hier war ein Bär", parse_html=True),
                radius=3,
                color=color,
                fill=True,
                fill_opacity=0.6
            ).add_to(sightings_map)

        if self.medians is not None:
            for median_lat, median_lon in self.medians:
                folium.CircleMarker(
                    location=[median_lat, median_lon],
                    radius=6,
                    color='blue',
                    fill=True,
                    fill_opacity=1.0
                ).add_to(sightings_map)

        if self.outliers is not None:
            for outlier_lat, outlier_lon in self.outliers:
                folium.CircleMarker(
                    location=[outlier_lat, outlier_lon],
                    radius=1,
                    color='black',
                    fill=True,
                    fill_opacity=0.6
                ).add_to(sightings_map)

        html_map = sightings_map.get_root().render()

        app = dash.Dash(__name__)

        app.layout = html.Div([
            html.H3(self.title),
            html.Iframe(srcDoc=html_map, width='100%', height='1000')
        ])

        app.run(debug=True)




