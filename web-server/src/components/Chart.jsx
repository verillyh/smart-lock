import CanvasJSReact from '@canvasjs/react-charts'
import dayjs from "dayjs"

var CanvasJSChart = CanvasJSReact.CanvasJSChart

function Chart({data}) {
    console.log("Chart data:", data)


    var options = {
        animationEnabled: true,
        zoomEnabled: true,
        title: {
            text: "Access logs"
        },
        data: [
            {
                type: "line",
                legendText: "Web unlock",
                showInLegend: true,
                dataPoints: data.webUnlocks
                },
                {
                type: "line",
                legendText: "Facial unlock",
                showInLegend: true,
                dataPoints: data.faceUnlocks
                }
        ]
    }

    return (
        <div>
            <CanvasJSChart options={options} />
        </div>
    )
}

export default Chart