"""Detrended agricultural deviation heatmap with climate hover context."""
import plotly.graph_objects as go
from src.bp4.features import reference


def event_heatmap(frame, outcome="Yield", region_order=None):
    short=outcome.lower();deviation=short+"_deviation_pct"
    actual="yield_value" if outcome=="Yield" else "production_ton"
    expected=short+"_trend";units="t/ha" if outcome=="Yield" else "tonnes"
    geographic=reference().region.drop_duplicates().tolist() if region_order is None else region_order
    present=set(frame.region)
    ordered=[region for region in geographic if region in present]+sorted(present-set(geographic))
    f=frame.copy()
    f["_region_order"]=f.region.map({region:i for i,region in enumerate(ordered)})
    f=f.sort_values(["_region_order","year"])
    pivot=f.pivot(index="region",columns="year",values=deviation).reindex(ordered)
    extent=max(float(f[deviation].abs().max()),.1) if f[deviation].notna().any() else 1.
    hover=("Region: %{y}<br>Year: %{x}<br>Actual "+outcome+": %{customdata[0]:.3f} "+units+
           "<br>Fitted trend value ("+outcome+"): %{customdata[1]:.3f} "+units+
           "<br>Deviation: %{customdata[2]:+.2f}%<br>Rainfall Anomaly: %{customdata[3]:+.2f}%"+
           "<br>Temperature Anomaly: %{customdata[4]:+.2f} C<extra></extra>")
    custom=f[[actual,expected,deviation,"rainfall_mm_anomaly","temperature_c_anomaly"]].to_numpy()
    cube=custom.reshape(len(pivot.index),len(pivot.columns),5)
    fig=go.Figure(go.Heatmap(x=pivot.columns,y=pivot.index,z=pivot.to_numpy(),customdata=cube,
                            zmin=-extent,zmax=extent,colorscale="RdBu_r",colorbar=dict(title="Deviation (%)"),
                            texttemplate="%{z:.1f}%",textfont=dict(size=12),
                            hovertemplate=hover,xgap=2,ygap=2))
    # Transparent markers supply a reliable black hover outline for each heatmap cell.
    fig.add_trace(go.Scatter(x=f.year,y=f.region,mode="markers",customdata=custom,name="Select a cell",showlegend=False,
                            marker=dict(symbol="square",size=38,color="rgba(0,0,0,0)",
                                        line=dict(color="rgba(0,0,0,0)",width=0)),hovertemplate=hover))
    fig.update_layout(title=f"Detrended {short} deviation (%)",height=max(350,85+len(pivot.index)*55),
                      margin=dict(l=20,r=30,t=50,b=45),
                      xaxis=dict(title="Year",dtick=1),yaxis=dict(title="Region",categoryorder="array",categoryarray=list(pivot.index),autorange="reversed"))
    return fig
