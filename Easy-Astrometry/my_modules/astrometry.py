
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.pyplot import axes, plot, ion, show
from matplotlib.figure import Figure
import matplotlib.lines as lines
from matplotlib.patches import Ellipse
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
import math
from functools import partial
import os
from pathlib import Path
import time

import my_modules.astromath as astromath #my own module
from my_modules.calibration import calibration # my own module
import my_modules.save as save #my own module
import my_modules.star as star #my own module
from my_modules.image_container import image_container
from my_modules.tooltip import CreateToolTip, _Tooltip_strings #not my own module, from the internet


import photutils
from photutils import datasets
from photutils import DAOStarFinder
from photutils import CircularAperture

from tkinter import *
from tkinter import filedialog
from tkinter import messagebox
from tkinter import LEFT

import astropy
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.visualization import SqrtStretch
from astropy.visualization.mpl_normalize import ImageNormalize
from astropy.visualization import PercentileInterval
from astropy.visualization import simple_norm
from astropy.table import Table

import ipywidgets as widgets
from IPython.display import display


class astrometry(image_container):

    """
    This class is resposible for all the calculations needed behind the Astrometry_root interface
    """

    def __init__(self,lights_path,GUI,menubar):
        super().__init__(lights_path,GUI,menubar)

        self.Tooltip_strings=_Tooltip_strings() # all the text for the tooltips are stored in a class

        ### mouse positions [x,y] ###
        self.clicked=[0,0]
        self.released=[0,0]
        self.current_position=[0,0]

        ### image properties ###
        self.header=self.headers[0] #import header of first image (only the first image is plotted)
        self.data=self.lights[0].copy() #import data
        self.image_scale_arcsec_per_pixel=self.header["scale"]

        # the actual plot, backend iherited from image_container
        self.doublevar_gamma=DoubleVar(self.GUI,value=1)
        im1=self.axes.imshow(self.data**-self.doublevar_gamma.get(),cmap="Greys",interpolation="none")

        self.perform_median_correction=True #irrelevant if dark_correction is true
        self.sigma=4.0
        self.threshold=9.0
        self.fwhm=4
        self.test_file_number=1
        self.output_folder_number=0
        self.moving_star_tolerance=0.1 #in arcsec
        self.distance_tolerance_arcsec=8
        self.distance_tolerance_pixel=3

        self.ref_i=0
        self.stars_searched=False
        self.same_stars_searched=False
        self.moving_stars_searched=False


        self.star_list=[]
        self.sources_list=[]

        self.sources=self.find_sources(save_files=False) # stars in image

        self.init_GUI()
        self.figure.canvas.draw()

        




    
    def get_test_file_number(self):
        return self.test_file_number
    

    def plot_all_sources(self):
        """
        This method plots all images that have been imported with its found stars
        
        """
        if self.light_imported==False:
            messagebox.showerror("Error", "import lights first")
        
        else:
            plt.clf()
            for i,data in enumerate(self.lights):
                fi=self.lights_path[i]

                _mean, median, std = sigma_clipped_stats(data, sigma=self.sigma) #get data statistic


                daofind = DAOStarFinder(fwhm=self.fwhm, threshold=self.threshold*std)
                sources=daofind(data)


                positions = np.transpose((sources['xcentroid'], sources['ycentroid']))
                apertures = CircularAperture(positions, r=4.)
                #norm = ImageNormalize(stretch=SqrtStretch()+PercentileInterval(70.))
                plt.figure(i+1)
                plt.title(os.path.basename(fi))
                plt.imshow(np.log(data), cmap='Greys', origin='lower', interpolation='none')
                for ii in range(len(sources['xcentroid'])):
                    plt.text(sources['xcentroid'][ii]+10, sources['ycentroid'][ii],sources['id'][ii])

                apertures.plot(color='blue', lw=1.5, alpha=0.5)
            plt.show()
                
    def test_plot(self,file_number):
        """Plot only the image with the given filenumber

        Args:
            file_number (int): number of file to plot (starting with 1)
        """
        if self.light_imported==False:
            messagebox.showerror("Error", "import lights first")
        
        else:
            data=self.lights[file_number-1]

            _mean, median, std = sigma_clipped_stats(data, sigma=self.sigma) #get data statistic
            #calibration

            daofind = DAOStarFinder(fwhm=self.fwhm, threshold=self.threshold*std)
            sources=daofind(data)
            positions = np.transpose((sources['xcentroid'], sources['ycentroid']))
            apertures = CircularAperture(positions, r=4.)
            #norm = ImageNormalize(stretch=SqrtStretch()+PercentileInterval(70.))
            plt.clf()
            plt.figure(1)
            plt.title("File number:"+str(file_number)+", found stars: "+str(len(sources['id'])))
            plt.imshow(np.log(data), cmap='Greys', origin='lower', interpolation='none')
            for ii in range(len(sources['xcentroid'])):
                plt.text(sources['xcentroid'][ii]+10, sources['ycentroid'][ii],sources['id'][ii])
            apertures.plot(color='blue', lw=1.5, alpha=0.5)
            plt.show()


    def find_sources(self,save_files=True): 
        """searches for stars in the loaded images. The sources are searched via DAOStarFinder.
           stars are saved in sources_list. Beforehands a calibration is done if activated.
           if save_files is True then the stars with its properties are also saved to a file.

        Args:
            save_files (bool): Decides if found stars are also written to file. Defaults to True.

        Returns:
            sources_list [list]: list of found stars. structure is sources_list[filenumber][starnumber]
        """
        if self.light_imported==False:
            messagebox.showerror("Error", "import lights first")
        
        else:
            sources_list=[]

            for i,data in enumerate(self.lights):
                print("finding stars in file #",str(i))

                _mean, median, std = sigma_clipped_stats(data, sigma=self.sigma) #get data statistic



                ####find stars in file################

                daofind = DAOStarFinder(fwhm=self.fwhm, threshold=self.threshold*std)
                sources=daofind(data) #sources is a astropy.table type, sources contains all the found stars by daofind algorithm
                   

                RA,DEC =astromath.return_coordinates_RA_DEC(self.headers[i], sources['xcentroid'], sources['ycentroid'])
                sources['RA/deg']=RA
                sources['DEC/deg']=DEC
                sources.sort('id')
                del sources['sky']; del sources['roundness1']
                del sources['roundness2']; del sources['npix']; del sources['sharpness']

                sources_list.append(sources) #write found stars of file into list
                
                if save_files==True:
                    _found=False
                    while _found==False: #define filename for output and find folder number
                        try:
                            os.mkdir(os.path.dirname(self.lights_path[0])+"/data_stars_"+str(self.output_folder_number))
                            _found=True
                        except FileExistsError:
                            self.output_folder_number+=1
            
                    sources.write(os.path.dirname(self.lights_path[i])+"/data_stars_"+str(self.output_folder_number)+"/"+Path(self.lights_path[i]).stem+".dat",format='ascii',overwrite=True)
                
            self.sources_list=sources_list
            self.stars_searched=True

                    




    def search_for_moving_stars(self):
        """
        currently under development. not finished yet.

        """
        if self.light_imported==False:
            messagebox.showerror("Error", "import lights first")
        
        else:
                
            if self.same_stars_searched==False:
                self.search_find()
            print("in search for moving stars")
            #star_list[star][file] type: star.star object
            ref_star_ID=-1 #error if not found

            #star_list[found stars in reference image][filenumber of related stars]  type=object star
            for i, star in enumerate(self.star_list): 
                print("i",i)

                dev_dec=[]
                dev_ra=[]
                rms=[]

                for s in star:  #browse through files in which star was found
                    dev_dec.append(s.get_dev_dec()*3600)
                    dev_ra.append(s.get_dev_ra()*3600)
                    rms.append(np.sqrt(s.get_dev_dec()**2+s.get_dev_ra()**2)*3600)
                    if s.get_dev_dec()==0.0:
                        ref_star_ID=s.get_ID()
                try:
                    m_dec,_=np.polyfit(range(len(dev_dec)),dev_dec,1)
                    m_ra,_ =np.polyfit(range(len(dev_ra)),dev_ra,1)
                    m_rms,_=np.polyfit(range(len(rms)),rms,1)
                except:
                    m_dec=0
                    m_ra=0
                    m_rms=0

                print("m_dec ", m_dec)
                print("m_ra ",m_ra)
                if (i<=2 or m_rms>self.moving_star_tolerance):
                    plt.figure(i) #too many
                    plt.xlabel("dev RA/arcsec")
                    plt.ylabel("dev DEC/arcsec")
                    plt.title("Reference image: "+str(self.ref_i)+" star id: "+str(ref_star_ID)+" m_dec "+str(np.round(m_dec,4))+" m_ra"+str(np.round(m_ra,4)))
                    plt.plot(dev_ra,dev_dec,linestyle='-',marker='+')
            self.test_plot(self.ref_i)
            plt.show()





    def search_same_stars(self):
        """
        This method searches for the same stars in different files and relates them.
        
        """
        if self.light_imported==False:
            messagebox.showerror("Error", "import lights first")
        
        else:
                
            self.star_list=[] #reset list
            # _number=0
            # _found=False

            # while _found==False: #define filename for output
            #     try:
            #         os.mkdir("data_stars"+str(_number))
            #         _found=True
            #     except FileExistsError:
            #         _number+=1
            
            #self.ref_i=math.floor(len(sources_list)/2.0) #middle entry 
            self.ref_i=astromath.get_image_with_highest_index(self.sources_list) # entry with highest number of stars
            print("reference image is image file number:",self.ref_i)

            for i in range(len(self.sources_list[self.ref_i]['id'])): #reference image, loop over stars i in reference image

                print("at star number",i)
                ra_ref=self.sources_list[self.ref_i]['RA/deg'][i] #RA of reference star nr. i
                dec_ref=self.sources_list[self.ref_i]['DEC/deg'][i] #DEC of reference star nr. i
                flux_ref=self.sources_list[self.ref_i]['flux'][i] # flux of reference star nr. i
                mag_ref=self.sources_list[self.ref_i]['mag'][i]
                id_ref=self.sources_list[self.ref_i]['id'][i]
                y_ref=self.sources_list[self.ref_i]['ycentroid'][i]
                x_ref=self.sources_list[self.ref_i]['xcentroid'][i]
                file_ref=os.path.basename(self.lights_path[self.ref_i])
                ref_star=star.star(star_ID=id_ref,ra=ra_ref,dec=dec_ref,mag=mag_ref,flux=flux_ref,x=x_ref,y=y_ref, filename=file_ref,dev_dec=0, dev_ra=0)
                star_files_list=[] #every reference star has an entry in here. All same stars from other files are added here
                



                for j, star_file in enumerate(self.sources_list): #loop over files j, exclude reference image

                    
                    if j!=self.ref_i:
                        for k in range(len(star_file['id'])): #loop over stars k in file j, !exclude reference image! maybe exclude distance=0 for that?
                        
                            #print("star number",k)
                            ra=star_file['RA/deg'][k]
                            dec=star_file['DEC/deg'][k]
                            x=star_file['xcentroid'][k]
                            y=star_file['ycentroid'][k]



                            if astromath.return_distance_arsec(ra,dec,ra_ref,dec_ref)<=self.distance_tolerance_arcsec:
                                #print("detected")
                                s=star.star(star_ID=int(star_file['id'][k]),x=x,y=y,ra=ra, dec=dec, flux=star_file['flux'][k],mag=star_file['mag'][k],filename=os.path.basename(self.lights_path[j]), dev_dec=dec-dec_ref,dev_ra=ra-ra_ref)
                                star_files_list.append(s)  #if star is found in file j, add to list, next file then
                    else:
                        star_files_list.append(ref_star) #so that reference frame is at correct position
                            


                # now print star_help_list to file
                ra_help=[]
                dec_help=[]
                flux_help= []
                id_help=[]
                mag_help=[]
                filename_help=[]
                dev_ra_help=[]
                dev_dec_help=[]
                rms_help=[]
                x_help=[]
                y_help=[]

                for s in star_files_list: #better call s.get()
                    ra_help.append(s.ra)
                    dec_help.append(s.dec)
                    x_help.append(s.xpos)
                    y_help.append(s.ypos)
                    flux_help.append(s.flux)
                    id_help.append(s.star_ID)
                    mag_help.append(s.mag)
                    filename_help.append(s.filename) # I dont know yet how to get this to file
                    dev_ra_help.append(s.dev_ra*3600)
                    dev_dec_help.append(s.dev_dec*3600)
                    rms_help.append(np.sqrt(s.dev_dec**2+s.dev_ra**2)*3600)


                header="  ID    	xpos      ypos        RA/deg	      DEC/deg	     flux	     mag 	  dev_ra/arcsec  dev_dec/arcsec  RMS/arcsec"
                #this is done for every star i  (s) 
                #save.save_to_file_5D(id_help,ra_help,dec_help, flux_help,mag_help, filename="data_stars"+str(_number)+"/id_"+str(sources_list[0]['id'][i]), acuracy=6,header=header)
                output=np.array([id_help,x_help,y_help, ra_help,dec_help, flux_help,mag_help,dev_ra_help, dev_dec_help, rms_help])
                #errors can occur here due to index overflow!
                save.save_to_file_ND(output, filename=os.path.dirname(self.lights_path[0])+"/data_stars_"+str(self.output_folder_number)+"/id_"+str(self.sources_list[self.ref_i]['id'][i])+"_ref_image_"+str(self.ref_i), acuracy=6,header=header)
                        
                self.star_list.append(star_files_list)
            
            print("done finding same stars")
            self.same_stars_searched=True

      



    def search_find(self):
        if self.light_imported==False:
            messagebox.showerror("Error", "import lights first")
        
        else:
            if self.stars_searched==False:
                self.find_sources(False)
            self.search_same_stars()

###############################################

    def search_without_platesolve(self):
        if self.light_imported==False:
            messagebox.showerror("Error", "import lights first")
        
        else:
            if self.same_stars_searched==False:
                self.search_find()


        # get header of one file and pixel center of all images

        ref_header=self.headers[0]
        number_of_files=len(self.lights)

        #star_list_reduced=self.star_list.where(len(self.star_list[:])==number_of_files)
        #star_list_reduced=[x for x in self.star_list[:] if len(x)==number_of_files]
        _star_list_reduced=[]

        #star_list[star][file] type: star.star object
        for i in range(len(self.star_list[:])): # loop through all stars to get number of files

            if len(self.star_list[i][:])==number_of_files:
                _star_list_reduced.append(self.star_list[i][:])


        x_center=[]
        y_center=[]

        for i in range(number_of_files):
            x=0
            y=0

            for j in range(len(_star_list_reduced[:])): # loop over all stars j and get xcenter for every file i
                x+=_star_list_reduced[j][i].get_xpos()
                y+=_star_list_reduced[j][i].get_ypos()
            print(" ")
            print(" ")
            x/=len(_star_list_reduced[:])
            y/=len(_star_list_reduced[:])
            x_center.append(x)
            y_center.append(y)
        
        print("center coordinates")
        print("x",x_center)
        print("y",y_center)

        #TODO loop over every star in every file and calculate new center weighted coordinate
        for x in self.star_list:
            pass

        #TODO calculate the mean deviation of xpos/ypos and plot if threshold is reached


        #star_list[star][file] type: star.star object

    def update_parameters(self,fwhm, sigma, threshold, distance_tolerance_arcsec, moving_star_tolerance,number): 
        self.fwhm=fwhm
        self.sigma=sigma
        self.threshold=threshold
        self.distance_tolerance_arcsec=distance_tolerance_arcsec
        self.moving_star_tolerance=moving_star_tolerance
        self.test_plot(number)

    def set_settings_tab(self):
        #TODO needs a rework

        ###############
        temp_gui=Tk(className="Set Parameters")
        temp_gui.geometry("500x300+0+0")

        t_fwhm=StringVar() #textvariables, will be updated each time
        t_fwhm.set(str(self.fwhm))
        t_sigma=StringVar()
        t_sigma.set(str(self.sigma))
        t_thr=StringVar()
        t_thr.set(str(self.threshold))
        t_dist_tolerance=StringVar()
        t_dist_tolerance.set(str(self.distance_tolerance_arcsec))
        t_number=StringVar()
        t_number.set(str(self.test_file_number))
        t_moving_star_tolerance=StringVar()
        t_moving_star_tolerance.set(str(self.moving_star_tolerance))
        
        _update_parameters=partial(self.update_parameters,t_fwhm,t_sigma,t_thr,t_dist_tolerance,t_moving_star_tolerance,t_number)
        _update_parameters()
        lfwhm=Label(temp_gui, text="fwhm in pixel")
        lfwhm.grid(row=0,column=0)
        Entry(temp_gui, textvariable=t_fwhm).grid(row=0,column=1)

        lsigma=Label(temp_gui,text="sigma")
        lsigma.grid(row=1,column=0)
        Entry(temp_gui, textvariable=t_sigma).grid(row=1,column=1)

        lthreshold=Label(temp_gui,text="threshold")
        lthreshold.grid(row=2,column=0)
        Entry(temp_gui, textvariable=t_thr).grid(row=2,column=1)
        

        ldist=Label(temp_gui,text="distance tolerance of stars in arcsec")
        ldist.grid(row=3,column=0)
        Entry(temp_gui, textvariable=t_dist_tolerance).grid(row=3,column=1)    

        lmstartol=Label(temp_gui,text="moving star tolerance")
        lmstartol.grid(row=5,column=0)
        Entry(temp_gui, textvariable=t_moving_star_tolerance).grid(row=5,column=1)

        limnum=Label(temp_gui,text="Image number for test")
        limnum.grid(row=4,column=0)
        Scale(temp_gui,from_=1, to=self.get_number_of_lights(), variable=t_number, orient=HORIZONTAL).grid(row=4,column=1)


        Button(temp_gui, text="set and test settings",command=_update_parameters).grid(row=6,column=0)

        __=CreateToolTip(lfwhm, self.Tooltip_strings.tooltip_fwhm)
        __=CreateToolTip(lsigma, self.Tooltip_strings.tooltip_sigma)
        __=CreateToolTip(lmstartol,self.Tooltip_strings.tooltip_tolerance)
        self.easy_astrometry_root.mainloop()

    def init_GUI(self):

        runmenu=Menu(self.menubar,tearoff=0)
        runmenu.add_command(label="Set parameters", command=self.set_settings_tab)
        runmenu.add_command(label="Plot all imported lights", command=self.plot_all_sources)
        runmenu.add_command(label="Search for stars and write to file", command=self.find_sources)
        runmenu.add_command(label="Search for same stars and write to file",command=self.search_find)
        runmenu.add_command(label="Search for moving targets", command=self.search_for_moving_stars)
        runmenu.add_command(label="Search for moving targets relative", command=self.search_without_platesolve)
        self.menubar.add_cascade(label="Astrometry", menu=runmenu)

        self.GUI.config(menu=self.menubar)
        self.GUI_Frame.pack()

