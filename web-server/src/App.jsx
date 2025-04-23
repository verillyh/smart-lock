import { useRef, useState, useEffect } from 'react'
import { io } from "socket.io-client"
import ImageUploading from 'react-images-uploading'

// TODO: Improve UI

function App() {
  const [unlock, setUnlock] = useState(false)
  const [images, setImages] = useState([])
  const socketRef = useRef(null)

  useEffect(() => {
    socketRef.current = io("http://localhost:3000")
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
      // Append file as form data
      formData.append("image", entry.file)
      // Upload image to server iteratively
      fetch("http://localhost:3000/upload", {
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
