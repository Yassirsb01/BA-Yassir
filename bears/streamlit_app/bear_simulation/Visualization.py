import dash
from dash import dcc, html
import plotly.graph_objects as go
import pandas as pd
from data.DatabaseConnection import DatabaseConnection
from data.WildlifeLocations import WildlifeLocations

dbc = DatabaseConnection("data/database.db")
wlc = WildlifeLocations(dbc)

timestamps = []
latitudes = []
longitudes = []
bear_ids = []

for entry in wlc.get_by_source_and_wildlife_id("Carpathians", 2, 40):
    _, _, bear_id, time, lat, lon, _ = entry
    timestamps.append(time)
    latitudes.append(lat)
    longitudes.append(lon)
    bear_ids.append(bear_id)

df = pd.DataFrame({
    'lat': latitudes,
    'lon': longitudes,
    'timestamp': pd.to_datetime(timestamps),
    'bear_id': bear_ids
})

# df = df.sort_values('timestamp')
# timestamps = df['timestamp'].sort_values().unique()

timestamps = df['timestamp']

frames = []
for t in timestamps:
    current = df[df['timestamp'] <= t]
    traces = []

    for bear in current['bear_id'].unique():
        bear_data = current[current['bear_id'] == bear]
        traces.append(go.Scattermap(
            lat=bear_data['lat'],
            lon=bear_data['lon'],
            mode='markers+lines',
            name=str(bear),
            marker=dict(size=8),
            line=dict(width=2)
        ))

    frames.append(go.Frame(data=traces, name=t.strftime("%Y-%m-%d %H:%M")))

init_traces = frames[0].data

fig = go.Figure(
    data=init_traces,
    layout=go.Layout(
        mapbox=dict(
            style='open-street-map',
            center=dict(lat=df['lat'].mean(), lon=df['lon'].mean()),
            zoom=5
        ),
        margin=dict(l=20, r=20, t=20, b=20),
        updatemenus=[dict(
            type='buttons',
            showactive=False,
            buttons=[
                dict(label='Play', method='animate',
                     args=[None, {"frame": {"duration": 800, "redraw": True},
                                  "fromcurrent": True}]),
                dict(label='Pause', method='animate',
                     args=[[None], {"frame": {"duration": 0}, "mode": "immediate"}])
            ]
        )],
        sliders=[{
            "steps": [
                {
                    "label": t.strftime('%Y-%m-%d %H:%M'),
                    "method": "animate",
                    "args": [[t.strftime('%Y-%m-%d %H:%M')],
                             {"frame": {"duration": 800, "redraw": True},
                              "mode": "immediate"}]
                } for t in timestamps
            ],
            "active": 0,
            "y": 0.00
        }]
    ),
    frames=frames
)

app = dash.Dash(__name__)
app.layout = html.Div([
    html.H1("Animated Bear Trajectories"),
    dcc.Graph(figure=fig, style={'height': '80vh', 'width': '100%'})
])

if __name__ == "__main__":
    app.run(debug=True)

