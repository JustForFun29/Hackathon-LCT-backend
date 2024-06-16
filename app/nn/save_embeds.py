import tensorflow_hub as hub
import numpy as np
import h5py


embed = hub.load("https://tfhub.dev/google/universal-sentence-encoder/4")

texts = [
    ['Generate a doctor profile.', 'CREATE_DOCTOR'],
    ['Add a doctor entry.', 'CREATE_DOCTOR'],
    ['Register a new doctor.', 'CREATE_DOCTOR'],
    ['Set up a doctor account.', 'CREATE_DOCTOR'],
    ['Form a doctor record.', 'CREATE_DOCTOR'],
    ['Create a new physician.', 'CREATE_DOCTOR'],
    ['Establish a doctor profile.', 'CREATE_DOCTOR'],
    ['Build a doctor entry.', 'CREATE_DOCTOR'],
    ['Initialize a doctor account.', 'CREATE_DOCTOR'],
    ['Produce a doctor profile.', 'CREATE_DOCTOR'],
    ['Create a doctor profile.', 'CREATE_DOCTOR'],
    ['Generate a new doctor entry.', 'CREATE_DOCTOR'],
    ['Insert a doctor profile.', 'CREATE_DOCTOR'],
    ['Input a doctor record.', 'CREATE_DOCTOR'],
    ['Build a new doctor profile.', 'CREATE_DOCTOR'],
    ['Add a doctor to the records.', 'CREATE_DOCTOR'],
    ['Record a new doctor profile.', 'CREATE_DOCTOR'],
    ['Log a doctor profile.', 'CREATE_DOCTOR'],
    ['Enroll a doctor record.', 'CREATE_DOCTOR'],
    ['Establish a new doctor account.', 'CREATE_DOCTOR'],
    ['Add a new doctor.', 'CREATE_DOCTOR'],
    ['Register a new physician.', 'CREATE_DOCTOR'],
    ['Insert a new doctor.', 'CREATE_DOCTOR'],
    ['Log a new doctor.', 'CREATE_DOCTOR'],
    ['Input a new physician.', 'CREATE_DOCTOR'],
    ['Create a new doctor profile.', 'CREATE_DOCTOR'],
    ['Add a new medical professional.', 'CREATE_DOCTOR'],
    ['Enroll a new doctor.', 'CREATE_DOCTOR'],
    ['Include a new doctor.', 'CREATE_DOCTOR'],
    ['Set up a new doctor.', 'CREATE_DOCTOR'],
    ['Form a new doctor record.', 'CREATE_DOCTOR'],
    ['Generate a new doctor account.', 'CREATE_DOCTOR'],
    ['Initialize a new physician profile.', 'CREATE_DOCTOR'],
    ['Create an entry for a new doctor.', 'CREATE_DOCTOR'],
    ['Record a new physician.', 'CREATE_DOCTOR'],
    ['Add a doctor to the new list.', 'CREATE_DOCTOR'],
    ['Register a doctor in the new section.', 'CREATE_DOCTOR'],
    ['Insert a physician in the new database.', 'CREATE_DOCTOR'],
    ['Create a new profile for a doctor.', 'CREATE_DOCTOR'],
    ['Log a new medical professional.', 'CREATE_DOCTOR'],
    ['Add a doctor to the database.', 'CREATE_DOCTOR'],
    ['Insert a doctor into the system.', 'CREATE_DOCTOR'],
    ['Register a doctor in the database.', 'CREATE_DOCTOR'],
    ['Upload doctor information to the database.', 'CREATE_DOCTOR'],
    ['Enter a doctor into the database.', 'CREATE_DOCTOR'],
    ['Save a doctor to the database.', 'CREATE_DOCTOR'],
    ['Log a doctor in the database.', 'CREATE_DOCTOR'],
    ['Record a doctor into the database.', 'CREATE_DOCTOR'],
    ['Input a doctor’s details into the database.', 'CREATE_DOCTOR'],
    ['File a doctor into the database.', 'CREATE_DOCTOR'],
    ['Add doctor details to the database.', 'CREATE_DOCTOR'],
    ['Enter doctor information into the database.', 'CREATE_DOCTOR'],
    ['Insert doctor data into the system.', 'CREATE_DOCTOR'],
    ['Register doctor credentials in the database.', 'CREATE_DOCTOR'],
    ['Save doctor details to the database.', 'CREATE_DOCTOR'],
    ['Log doctor information in the database.', 'CREATE_DOCTOR'],
    ['Record doctor data into the database.', 'CREATE_DOCTOR'],
    ['Input doctor credentials into the database.', 'CREATE_DOCTOR'],
    ['File doctor details into the database.', 'CREATE_DOCTOR'],
    ['Store a doctor in the database.', 'CREATE_DOCTOR'],
    ['Remove a doctor profile.', 'REMOVE_DOCTOR'],
    ['Erase a doctor entry.', 'REMOVE_DOCTOR'],
    ['Delete a physician.', 'REMOVE_DOCTOR'],
    ['Remove a doctor account.', 'REMOVE_DOCTOR'],
    ['Delete a doctor record.', 'REMOVE_DOCTOR'],
    ['Eliminate a doctor profile.', 'REMOVE_DOCTOR'],
    ['Remove a doctor listing.', 'REMOVE_DOCTOR'],
    ['Delete a medical professional.', 'REMOVE_DOCTOR'],
    ['Remove a physician.', 'REMOVE_DOCTOR'],
    ['Delete a doctor entry.', 'REMOVE_DOCTOR'],
    ['Delete a doctor.', 'REMOVE_DOCTOR'],
    ['Erase a doctor.', 'REMOVE_DOCTOR'],
    ['Remove a physician.', 'REMOVE_DOCTOR'],
    ['Eliminate a doctor.', 'REMOVE_DOCTOR'],
    ['Delete a doctor profile.', 'REMOVE_DOCTOR'],
    ['Remove a doctor record.', 'REMOVE_DOCTOR'],
    ['Erase a doctor profile.', 'REMOVE_DOCTOR'],
    ['Remove a medical professional.', 'REMOVE_DOCTOR'],
    ['Delete a physician profile.', 'REMOVE_DOCTOR'],
    ['Remove a doctor listing.', 'REMOVE_DOCTOR'],
    ['Remove a doctor from the database.', 'REMOVE_DOCTOR'],
    ['Delete a doctor entry from the database.', 'REMOVE_DOCTOR'],
    ['Erase a doctor from the system.', 'REMOVE_DOCTOR'],
    ['Remove a physician from the database.', 'REMOVE_DOCTOR'],
    ['Delete doctor data from the database.', 'REMOVE_DOCTOR'],
    ['Eliminate a doctor from the database.', 'REMOVE_DOCTOR'],
    ['Delete doctor details from the database.', 'REMOVE_DOCTOR'],
    ['Remove a doctor profile from the database.', 'REMOVE_DOCTOR'],
    ['Erase a doctor record from the database.', 'REMOVE_DOCTOR'],
    ['Delete a physician from the database.', 'REMOVE_DOCTOR'],
]

text_data = [text[0] for text in texts]
labels = [text[1] for text in texts]

embeddings = embed(text_data)

with h5py.File('embeddings/doctor_embeddings.h5', 'w') as f:
    f.create_dataset('embeddings', data=embeddings.numpy())
    dt = h5py.special_dtype(vlen=str)
    f.create_dataset('texts', data=np.array(text_data, dtype=dt))
    f.create_dataset('labels', data=np.array(labels, dtype=dt))

print("Embeddings and labels have been saved to doctor_embeddings.h5")
