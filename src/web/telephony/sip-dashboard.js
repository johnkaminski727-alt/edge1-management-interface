async function loadData() {

    try {

        const health = await fetch(
            "http://127.0.0.1:8095/telephony/status"
        );

        const interconnects = await fetch(
            "http://127.0.0.1:8095/telephony/interconnects"
        );


        document.getElementById(
            "health"
        ).textContent =
            JSON.stringify(
                await health.json(),
                null,
                2
            );


        document.getElementById(
            "interconnects"
        ).textContent =
            JSON.stringify(
                await interconnects.json(),
                null,
                2
            );


    } catch (error) {

        document.getElementById(
            "health"
        ).textContent =
            "Unable to load SIP API: " + error;

    }

}


loadData();
