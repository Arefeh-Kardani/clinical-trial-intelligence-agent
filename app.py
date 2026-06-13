import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from collections import Counter

st.set_page_config(page_title="Clinical Trial Intelligence Agent", layout="wide")

st.title("Clinical Trial Intelligence Agent")
st.write("Search clinical trial data and generate automated pharma/business insights.")


def safe_join(value):
    if isinstance(value, list) and len(value) > 0:
        return ", ".join(value)
    return "Not Available"


def extract_year(date_value):
    if isinstance(date_value, str) and len(date_value) >= 4 and date_value[:4].isdigit():
        return int(date_value[:4])
    return None


def fetch_trials(condition, max_pages=25):
    url = "https://clinicaltrials.gov/api/v2/studies"
    trials = []
    page_token = None
    page_count = 0

    while page_count < max_pages:
        params = {
            "query.cond": condition,
            "pageSize": 1000,
            "format": "json",
            "countTotal": "true"
        }

        if page_token:
            params["pageToken"] = page_token

        response = requests.get(url, params=params)
        data = response.json()

        for study in data.get("studies", []):
            protocol = study.get("protocolSection", {})

            identification = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            design = protocol.get("designModule", {})
            sponsor = protocol.get("sponsorCollaboratorsModule", {})
            conditions = protocol.get("conditionsModule", {})
            arms = protocol.get("armsInterventionsModule", {})
            locations = protocol.get("contactsLocationsModule", {})

            nct_id = identification.get("nctId", "Not Available")
            start_date = status.get("startDateStruct", {}).get("date", "Not Available")

            interventions = arms.get("interventions", [])
            intervention_names = [
                i.get("name", "Not Available")
                for i in interventions
            ]

            location_list = locations.get("locations", [])
            countries = list(set([
                loc.get("country")
                for loc in location_list
                if loc.get("country")
            ]))

            trials.append({
                "NCT ID": nct_id,
                "Title": identification.get("briefTitle", "Not Available"),
                "Status": status.get("overallStatus", "Not Available"),
                "Phase": safe_join(design.get("phases", [])),
                "Sponsor": sponsor.get("leadSponsor", {}).get("name", "Not Available"),
                "Conditions": safe_join(conditions.get("conditions", [])),
                "Interventions": safe_join(intervention_names),
                "Countries": safe_join(countries),
                "Start Date": start_date,
                "Completion Date": status.get("completionDateStruct", {}).get("date", "Not Available"),
                "Link": f"https://clinicaltrials.gov/study/{nct_id}"
            })

        page_token = data.get("nextPageToken")
        page_count += 1

        if not page_token:
            break

    return pd.DataFrame(trials)


def generate_agent_insights(df, condition):
    insights = []

    if df.empty:
        return ["No trials were found. Try another condition name."]

    insights.append(f"The agent found {len(df)} clinical trials related to {condition}.")

    top_status = df["Status"].value_counts().idxmax()
    top_phase = df["Phase"].value_counts().idxmax()
    top_sponsor = df["Sponsor"].value_counts().idxmax()

    insights.append(f"The most common trial status is {top_status}.")
    insights.append(f"The most common clinical phase is {top_phase}.")
    insights.append(f"The most frequent sponsor is {top_sponsor}.")

    if top_status == "RECRUITING":
        insights.append("This suggests active current research in this disease area.")
    elif top_status == "COMPLETED":
        insights.append("This suggests there is strong historical trial data available.")

    insights.append("Suggested next analysis: review top sponsors, countries, phases, interventions, and research activity over time.")

    return insights


st.sidebar.header("Search Settings")

condition = st.sidebar.text_input("Enter disease or condition", "breast cancer")

max_pages = st.sidebar.slider(
    "Number of API pages to fetch",
    min_value=1,
    max_value=25,
    value=2
)

search_button = st.sidebar.button("Search Trials")


if search_button:
    with st.spinner("Fetching clinical trial data..."):
        df = fetch_trials(condition, max_pages)

    st.success(f"Fetched {len(df)} trial records.")

    if not df.empty:
        st.subheader("Key Metrics")

        completed_count = (df["Status"] == "COMPLETED").sum()
        recruiting_count = (df["Status"] == "RECRUITING").sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Trials", len(df))
        col2.metric("Completed Trials", completed_count)
        col3.metric("Recruiting Trials", recruiting_count)
        col4.metric("Unique Sponsors", df["Sponsor"].nunique())

        st.subheader("Agent Summary")

        for insight in generate_agent_insights(df, condition):
            st.write(f"- {insight}")

        st.subheader("Clinical Trial Data")

        st.dataframe(
            df,
            column_config={
                "Link": st.column_config.LinkColumn("ClinicalTrials.gov Link")
            },
            use_container_width=True
        )

        st.subheader("Top Sponsors")

        sponsor_counts = df["Sponsor"].value_counts().head(10).reset_index()
        sponsor_counts.columns = ["Sponsor", "Number of Trials"]

        fig_sponsor = px.bar(
            sponsor_counts,
            x="Sponsor",
            y="Number of Trials",
            title="Top 10 Sponsors"
        )
        st.plotly_chart(fig_sponsor, use_container_width=True)

        st.subheader("Trial Status Distribution")

        status_counts = df["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Number of Trials"]

        fig_status = px.bar(
            status_counts,
            x="Status",
            y="Number of Trials",
            title="Trial Status Distribution"
        )
        st.plotly_chart(fig_status, use_container_width=True)

        st.subheader("Trial Phase Distribution")

        phase_counts = df["Phase"].value_counts().reset_index()
        phase_counts.columns = ["Phase", "Number of Trials"]

        fig_phase = px.bar(
            phase_counts,
            x="Phase",
            y="Number of Trials",
            title="Trial Phase Distribution"
        )
        st.plotly_chart(fig_phase, use_container_width=True)

        st.subheader("Country Analysis")

        all_countries = []

        for countries in df["Countries"].dropna():
            country_list = [
                c.strip()
                for c in countries.split(",")
                if c.strip() != "Not Available"
            ]
            all_countries.extend(country_list)

        if all_countries:
            country_df = pd.DataFrame(
                Counter(all_countries).most_common(15),
                columns=["Country", "Number of Trials"]
            )

            fig_country = px.bar(
                country_df,
                x="Country",
                y="Number of Trials",
                title="Top Countries"
            )
            st.plotly_chart(fig_country, use_container_width=True)
        else:
            st.info("No country data available.")

        st.subheader("Intervention Analysis")

        all_interventions = []

        for interventions in df["Interventions"].dropna():
            intervention_list = [
                i.strip()
                for i in interventions.split(",")
                if i.strip() != "Not Available"
            ]
            all_interventions.extend(intervention_list)

        if all_interventions:
            intervention_df = pd.DataFrame(
                Counter(all_interventions).most_common(15),
                columns=["Intervention", "Number of Trials"]
            )

            fig_intervention = px.bar(
                intervention_df,
                x="Intervention",
                y="Number of Trials",
                title="Top Interventions"
            )
            st.plotly_chart(fig_intervention, use_container_width=True)
        else:
            st.info("No intervention data available.")

        st.subheader("Research Activity Over Time")

        df["Start Year"] = df["Start Date"].apply(extract_year)
        year_df = df.dropna(subset=["Start Year"])

        if not year_df.empty:
            year_counts = year_df["Start Year"].value_counts().sort_index().reset_index()
            year_counts.columns = ["Start Year", "Number of Trials"]

            fig_year = px.line(
                year_counts,
                x="Start Year",
                y="Number of Trials",
                title=f"Trials by Start Year for {condition}"
            )
            st.plotly_chart(fig_year, use_container_width=True)
        else:
            st.info("No start year data available.")

        st.subheader("Export Data")

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download trial data as CSV",
            data=csv,
            file_name=f"{condition}_clinical_trials.csv",
            mime="text/csv"
        )