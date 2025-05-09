import { useRef, useState, useEffect } from 'react'
import { io } from "socket.io-client"
import Chart from "./components/Chart"
import ImageUploading from 'react-images-uploading'

// TODO: Improve UI

function App() {
  const serverUrl = "http://192.168.20.11:3000"
  const [unlock, setUnlock] = useState(false)
  const [chartData, setChartData] = useState([])
  const [personName, setPersonName] = useState("Vincent")
  const [images, setImages] = useState([])
  const socketRef = useRef(null)

  useEffect(() => {
    socketRef.current = io(serverUrl)
    
    socketRef.current.on("connect", () => {
      console.log("Connected to server")
    })

    socketRef.current.on("access_logs", (data) => {
      console.log("New access logs entry:", data)

      refreshData(data)
    })
    // Show data on graph
    socketRef.current.emit("refresh")
    
    return () => {
      socketRef.current.disconnect()
    }
  }, [])


  // Functions
  const refreshData = data => {
    let face_count = []
    let web_count = []
    
    data.forEach(entry => {
      face_count.push({
        "y": entry.face_count,
        "label": entry.date
      })
      web_count.push({
        "y": entry.web_count,
        "label": entry.date
      })

    })

    setChartData({"faceUnlocks": face_count, "webUnlocks": web_count})
  }

  const handleUnlock = (state) => {
    setUnlock(state)

    if (socketRef.current) {
      socketRef.current.emit("unlock", state)
    }
  }

  // Function to handle image submission
  const submitPictures = (data) => {
    const formData = new FormData()

    // For each image file
    data.forEach((entry) => {
      // Populate form data
      formData.append("personName", personName)
      formData.append("image", entry.file)
      // Upload image to server iteratively
      fetch(serverUrl + "/upload", {
        method: "POST",
        body: formData,
      })
      .then((response) => {
        if (response.ok) {
          console.log("Images uploaded successfully")
        } else {
          console.error("Error uploading images")
        }
      })
      .catch((error) => {
        console.error("Error:", error)
      })
    })
  }

  const onRefresh = () => {
    if (socketRef.current) {
      socketRef.current.emit("refresh")
    }
  } 

  return (
    <>
      <main className='flex flex-col items-center py-4 text-2xl w-screen'>
        <p className='m-auto'>Smart Lock</p>
        <ImageUploading
          multiple
          value={images}
          onChange={(imageList) => setImages(imageList)}
          maxNumber={69}
          dataURLKey="data_url"
          >
            {({
              imageList,
              onImageUpload,
              onImageRemoveAll,
              onImageUpdate,
              onImageRemove,
              isDragging,
              dragProps
            }) => (
              <div className='flex flex-col items-center'>
                <button className='button bg-neutral-400 rounded p-1' onClick={onImageUpload}>Upload Image</button>
                <button className='button bg-neutral-400 rounded p-1 mt-3' onClick={onRefresh}>Refresh data</button>
                <div className='flex flex-row gap-4'>
                  {imageList.map((image, index) => (
                    <div key={index} className='relative'>
                      <img src={image['data_url']} alt="" width="100" />
                      <button className='absolute top-0 right-0' onClick={() => onImageRemove(index)}>X</button>
                    </div>
                  ))}
                </div>
                <label htmlFor="name">Person name</label>
                <input type="text" name='name' id='name' value={personName} onChange={e => setPersonName(e.target.value)} className='border' />
                <button className='button bg-neutral-400 rounded p-1' onClick={() => submitPictures(imageList)}>Submit Pictures</button>
              </div>
            )}
          </ImageUploading>
        <div className='flex flex-row justify-center items-center gap-4'>
          <button onClick={() => handleUnlock(true)} type="button" className='button bg-green-500'>Unlock</button>
        </div>

        <div className='flex flex-row'>
          <Chart data={chartData} />
        </div>
      </main>
    </>
  )
}

export default App
