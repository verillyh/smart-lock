import { useRef, useState, useEffect } from 'react'
import { io } from "socket.io-client"
import ImageUploading from 'react-images-uploading'

// TODO: Improve UI

function App() {
  const serverUrl = "http://192.168.67.226:3000"
  const [unlock, setUnlock] = useState(false)
  const [personName, setPersonName] = useState("Vincent")
  const [images, setImages] = useState([])
  const socketRef = useRef(null)

  useEffect(() => {
    socketRef.current = io(serverUrl)
    socketRef.current.on("connect", () => {
      console.log("Connected to server")
    })

    return () => {
      socketRef.current.disconnect()
    }
  }, [])

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
                <button className='button' onClick={onImageRemoveAll}>Remove All Images</button>
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
          <button onClick={() => handleUnlock(false)} type="button" className='button bg-red-500'>Lock</button>
        </div>
      </main>
    </>
  )
}

export default App
