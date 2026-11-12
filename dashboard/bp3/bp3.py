"""BP3 entry point. Replace the content here when the BP3 mart is available."""
import streamlit as st

st.markdown('<div class="eyebrow">BP3 / PREDICTIVE ANALYTICS</div>', unsafe_allow_html=True)
st.title("Rice production forecasting")
st.markdown("Estimate next year’s production from historical data and evaluate forecast errors to support supply planning.")
st.info("The BP3 dashboard is in development. Forecasts are not available yet.", icon=":material/construction:")
st.subheader("Key question")
st.markdown("How might production change next year? How accurate are forecasts in historical backtests, and which contingency plans should be considered?")
