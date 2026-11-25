"""Descriptive annual production and temperature overlays, without inference."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative
from plotly.subplots import make_subplots
from src.bp4.features import reference


def order_region_legends(fig, regions):
    """Order region entries geographically without changing colors or plotted data."""
    ranks={region:i for i,region in enumerate(regions)}
    found=False
    for trace in fig.data:
        region=trace.legendgroup if trace.legendgroup in ranks else trace.name
        if region in ranks:
            trace.legendrank=ranks[region]
            found=True
    if found:
        fig.update_layout(legend_traceorder="normal")
    return fig


def add_regional_trends(fig, frame, x, y, minimum=8):
    """Descriptive OLS lines over observed ranges; never interpolate missing pairs."""
    colors={trace.name:trace.marker.color for trace in fig.data if trace.mode=="markers"}
    for region,g in frame.groupby("region"):
        valid=g[[x,y]].replace([np.inf,-np.inf],np.nan).dropna()
        if len(valid)<minimum or valid[x].nunique()<2:
            continue
        slope,intercept=np.polyfit(valid[x].to_numpy(dtype=float),valid[y].to_numpy(dtype=float),1)
        xs=np.linspace(valid[x].min(),valid[x].max(),50)
        fig.add_trace(go.Scatter(x=xs,y=intercept+slope*xs,mode="lines",name=str(region)+" trend",
                                legendgroup=str(region),showlegend=False,
                                line=dict(color=colors.get(region),dash="dash",width=2),
                                meta=dict(role="linear_trend",region=str(region),n=len(valid)),
                                hovertemplate=str(region)+" OLS trend<br>x=%{x:.2f}<br>Fitted change=%{y:.2f}%<extra></extra>"))
    return fig


def national_temperature(regional, baseline, minimum=8):
    return national_climate(regional,baseline,minimum,"temperature_c")


def national_rainfall(regional, baseline, minimum=8):
    return national_climate(regional,baseline,minimum,"rainfall_mm")


def national_climate(regional, baseline, minimum, column):
    rows=[]
    for year,g in regional.groupby("year"):
        valid=g[column].notna() & g.area_ha.gt(0)
        complete=len(g)==7 and g.region.nunique()==7 and valid.all()
        rows.append({"year":year,column:np.average(g[column],weights=g.area_ha) if complete else np.nan})
    result=pd.DataFrame(rows).sort_values("year")
    reference=result[result.year.between(*baseline)][column].dropna()
    required=max(minimum,int(np.ceil((baseline[1]-baseline[0]+1)*.9)))
    mean=reference.mean() if len(reference)>=required else np.nan
    result[column+"_anomaly"]=(result[column]/mean-1)*100 if column=="rainfall_mm" and mean>0 else result[column]-mean if column=="temperature_c" else np.nan
    return result


def production_temperature_figure(regional, temperature, anomaly=False, national=True, climate="Temperature", outcome="Production"):
    """Stack actual regional tonnes to annual totals; temperature uses a separate axis."""
    fig=make_subplots(specs=[[{"secondary_y":True}]])
    palette={region:qualitative.Safe[i%len(qualitative.Safe)] for i,region in enumerate(sorted(reference().region.unique()))}
    totals=regional.groupby("year").production_ton.agg(lambda s:s.sum(min_count=len(s)))
    is_yield=outcome=="Yield"
    bars=regional
    national_area=regional.groupby("year").area_ha.agg(lambda s:s.sum(min_count=len(s))) if is_yield and national else None
    if is_yield and national:
        bars=pd.DataFrame({'year':totals.index,'region':'National yield','yield_value':totals.div(national_area.where(national_area.gt(0))).to_numpy()})
    for i,(region,g) in enumerate(bars.groupby("region",sort=True)):
        g=g.sort_values("year")
        if is_yield:
            values=g.yield_value
            fig.add_trace(go.Bar(x=g.year,y=values,name=region,marker_color=palette.get(region,qualitative.Safe[i%len(qualitative.Safe)]),
                                customdata=g.yield_value.to_numpy(),
                                hovertemplate="%{x}<br>%{fullData.name}<br>Rice yield: %{y:.3f} t/ha<extra></extra>"),secondary_y=False)
            continue
        fig.add_trace(go.Bar(x=g.year,y=g.production_ton,name=region,
                            marker_color=palette.get(region,qualitative.Safe[i%len(qualitative.Safe)]),
                            customdata=np.column_stack([g.production_ton,g.year.map(totals)]),
                            hovertemplate="%{x}<br>%{fullData.name}<br>Production: %{customdata[0]:,.0f} tonnes"+
                                          ("<br>National production: %{customdata[1]:,.0f} tonnes" if national else "")+"<extra></extra>"),secondary_y=False)
    temperature=temperature.sort_values("year")
    rainfall=climate=="Rainfall"
    column=("rainfall_mm" if rainfall else "temperature_c")+("_anomaly" if anomaly else "")
    label=("Rainfall anomaly" if anomaly else "Annual rainfall") if rainfall else ("Temperature anomaly" if anomaly else "Average temperature")
    unit=("%" if anomaly else "mm") if rainfall else "C"
    actual_column="rainfall_mm" if rainfall else "temperature_c"
    actual_unit="mm" if rainfall else "C"
    fig.add_trace(go.Scatter(x=temperature.year,y=temperature[column],name=label,mode="lines+markers",
                            line=dict(color="#3989C9" if rainfall else "#E45756",width=3),connectgaps=False,
                            customdata=temperature[actual_column].to_numpy(),
                            hovertemplate="%{x}<br>"+label+": %{y:.2f} "+unit+
                                          ("<br>Actual: %{customdata:.2f} "+actual_unit if anomaly else "")+"<extra></extra>"),secondary_y=True)
    fig.update_layout(barmode="stack",hovermode="x unified",title="Rice "+outcome.lower()+" & "+climate.lower(),
                      legend=dict(orientation="h",y=-.22),xaxis=dict(title="Year",dtick=1))
    axis_title=("National rice yield (t/ha)" if national else "Rice yield (t/ha)") if is_yield else ("National rice production (tonnes)" if national else "Rice production (tonnes)")
    fig.update_yaxes(title_text=axis_title,secondary_y=False,rangemode="tozero",tickformat=",.2f" if is_yield else ",.0f")
    fig.update_yaxes(title_text=label+" ("+unit+")",secondary_y=True,showgrid=False)
    if anomaly:
        values=temperature[column].replace([np.inf,-np.inf],np.nan).dropna()
        if len(values):
            extent=max(float(values.abs().max())*1.15,.1 if rainfall else .01)
            fig.update_yaxes(range=[-extent,extent],secondary_y=True,tickformat="+.2f")
            fig.add_hline(y=0,secondary_y=True,line_dash="dot",line_color="gray",line_width=1)
    regions=reference().region.drop_duplicates().tolist()
    ranks={region:i for i,region in enumerate(regions)}
    bars=sorted((t for t in fig.data if t.type=="bar"),key=lambda t:ranks.get(t.name,len(ranks)),reverse=True)
    fig.data=tuple(bars)+tuple(t for t in fig.data if t.type!="bar")
    order_region_legends(fig,regions)
    return fig


def production_both_weather_figure(regional, temperature, rainfall, temperature_anomaly=False,
                                  rainfall_anomaly=False,national=True,outcome="Production"):
    """Keep weather on independent axes because C and mm/% are different units."""
    fig=production_temperature_figure(regional,temperature,temperature_anomaly,national,outcome=outcome)
    rain_fig=production_temperature_figure(regional,rainfall,rainfall_anomaly,national,climate="Rainfall",outcome=outcome)
    rain_trace=go.Scatter(rain_fig.data[-1])
    rain_trace.yaxis="y3"
    fig.add_trace(rain_trace)
    rain_axis=rain_fig.layout.yaxis2.to_plotly_json()
    rain_axis.update(anchor="free",overlaying="y",side="right",position=.98,
                     tickfont=dict(color="#3989C9"))
    rain_axis["title"]["font"]=dict(color="#3989C9")
    fig.update_layout(title="Rice "+outcome.lower()+", temperature & rainfall",
                      xaxis=dict(domain=[0,.73]),
                      yaxis2=dict(anchor="free",overlaying="y",side="right",position=.77,
                                  tickfont=dict(color="#E45756"),title_font=dict(color="#E45756")),
                      yaxis3=rain_axis)
    if rainfall_anomaly and rainfall.rainfall_mm_anomaly.notna().any():
        fig.add_shape(type="line",xref="x domain",x0=0,x1=1,yref="y3",y0=0,y1=0,
                      line=dict(color="#3989C9",dash="dot",width=1))
    return fig
