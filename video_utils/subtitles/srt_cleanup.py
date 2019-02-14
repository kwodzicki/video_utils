import os, re;
def srt_cleanup( fname, verbose = False ):
	'''
	Name:
	  srt_cleanup
	Purpose:
	  A python function to replace J' characters at the beginning or ending of 
	  a subtitle line with a musical note character as this seems to be an issue 
	  with the vobsub2srt program.
	Inputs:
	  fname  : Path to a file. This file will be overwritten.
	Outputs:
	  Outputs a file to the same name as input, i.e., over writes the file.
	Keywords:
	  verbose : Set to increase verbosity.
	Author and History:
	  Kyle R. Wodzicki     Created 27 Dec. 2016
	'''
	out_file = fname + '.tmp';
	iid, oid, i, music = open(fname, 'r'), open(out_file, 'w'), 0, False;         # Open input file for reading and output file for writing, initialize counter
	for in_line in iid:
		i+=1;
		line = in_line.rstrip();
		if len(line) > 0:
			# Checking for J' at beginning or end of line, likely music note
			if line[:4]  == 'J\xe2\x80\x98':                                          # If the J' is at the beginning of the line
				if verbose: print( 'Line: '+str(i)+' changed\n  '+line ); 							# Print some output
				line = '\xe2\x99\xaa' + line[4:];																				# Replace J' with the music note
				if line[-4:] == 'J\xe2\x80\x98':             			                      # If the end of the line is J'
					line = line[:-4]  + '\xe2\x99\xaa';																		# Replace J' with the music note
				if verbose: print( '  '+line );																				  # Print some output
				music = True;                                                           # Set music to True
			elif line[-4:] == 'J\xe2\x80\x98':       			                            # Else, if the J' is at the end of the line
				if verbose: print( 'Line: '+str(i)+' changed\n  '+line );  							# Print some output
				line = line[:-4]  + '\xe2\x99\xaa';                                     # Replace the J' with the music note
				if verbose: print( '  '+line );  																				# Print some output
				music = True;                                                           # Set music to True
			# Check for ,' anywhere in line, Likely music note
			elif ',\xe2\x80\x98' in line:                                             # If ,' is in the line
				if line[:4]  == ',\xe2\x80\x98' and line[-1] == ';':                    # If the first characters are ,' and the last character is ;, then last character should be music note 
					line = line[:-1]+' \xe2\x99\xaa';                                     # Replace last character with a music note
				line = line.replace(',\xe2\x80\x98', '\xe2\x99\xaa ');                  # Replace the ,' with a music note
				music = True;                                                           # Set music to True
			elif line[0] == "J" and line[-1] == "J":                                  # If line begins and ends with capital J, then likely music notes
				line = '\xe2\x99\xaa'+line[1:-2]+' \xe2\x99\xaa';                       # Replace the J's with music notes
				music = True;                                                           # Set music to True
			elif line[:2] == 'J ':
				line = '\xe2\x99\xaa' + line[1:];
				music = True;                                                           # Set music to True
			elif re.match(re.compile(r'J[A-Z]{1}'), line):                            # If "J" is found followed by another capital letter, likely is a music note.
				line = '\xe2\x99\xaa ' + line[1:];
				music = True;
			elif music is True:                                                       # If music is True, that means this line is a continuation of previous line
				if line[-1] == ';':
					line = line[:-1] + ' \xe2\x99\xaa';                                   # If the last character is a semi colon, replace with music note
				elif line[-5:] == ', \xe2\x80\x98':                                     # If the last characters are ", '" then replace with music note
					line = line[:-5] + ' \xe2\x99\xaa';    
				elif line[-4:] == ',\xe2\x80\x98':                                      # If last characters are ",'" then replace with music note 
					line = line[:-4] + ' \xe2\x99\xaa'; 
				elif line[-4:] == '\xe2\x80\x99J':                                      # If last characters are "'J" then replace with music note
					line = line[:-4] + ' \xe2\x99\xaa';
				elif line[-4:] == 'J\xe2\x80\x98':             			                    # If the end of the line is J'
					line = line[:-4]  + '\xe2\x99\xaa';																		# Replace J' with the music note
				elif line[-2:]  == ' J':                                                # If last characters are " J" then replace with music note
					line = line[:-2] + ' \xe2\x99\xaa';
				elif line[-1]  == 'J':                                                  # If last character is "J" then replace with music note
					line = line[:-1] + ' \xe2\x99\xaa';
		else:
			music = False;                                                           # Set music to false as line was blank meaning end of that subtitle
		oid.write(line + '\n');
	iid.close();
	oid.close();
	os.rename( out_file, fname );
	return 0;																																			# Return zero